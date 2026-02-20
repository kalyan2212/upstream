terraform {
  required_version = ">= 1.6.0"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.90"
    }
  }

  # Remote backend — Terraform state stored in Azure Blob Storage.
  # The storage account is created by scripts/bootstrap_tfstate.sh BEFORE
  # the first terraform init.
  backend "azurerm" {
    resource_group_name  = "rg-tfstate-upstream"
    storage_account_name = "sttfstateupstream001"
    container_name       = "tfstate"
    key                  = "upstream.terraform.tfstate"
  }
}

provider "azurerm" {
  features {}
}

# ── Resource Group ────────────────────────────────────────────────────────────
resource "azurerm_resource_group" "rg" {
  name     = var.resource_group_name
  location = var.location
  tags     = local.tags
}

# ── Networking ────────────────────────────────────────────────────────────────
resource "azurerm_virtual_network" "vnet" {
  name                = "vnet-upstream-${var.environment}"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  address_space       = ["10.0.0.0/16"]
  tags                = local.tags
}

resource "azurerm_subnet" "app_subnet" {
  name                 = "snet-app"
  resource_group_name  = azurerm_resource_group.rg.name
  virtual_network_name = azurerm_virtual_network.vnet.name
  address_prefixes     = ["10.0.1.0/24"]
}

# ── Network Security Group ────────────────────────────────────────────────────
resource "azurerm_network_security_group" "nsg" {
  name                = "nsg-upstream-${var.environment}"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  tags                = local.tags

  # SSH — restricted to deployer IP or GitHub Actions (update as needed)
  security_rule {
    name                       = "Allow-SSH"
    priority                   = 100
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_range     = "22"
    source_address_prefix      = "*"
    destination_address_prefix = "*"
  }

  # HTTP — public traffic via Load Balancer
  security_rule {
    name                       = "Allow-HTTP"
    priority                   = 110
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_range     = "80"
    source_address_prefix      = "*"
    destination_address_prefix = "*"
  }

  # Streamlit port — needed for LB health probe
  security_rule {
    name                       = "Allow-Streamlit"
    priority                   = 120
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_range     = "8501"
    source_address_prefix      = "*"
    destination_address_prefix = "*"
  }
}

resource "azurerm_subnet_network_security_group_association" "nsg_assoc" {
  subnet_id                 = azurerm_subnet.app_subnet.id
  network_security_group_id = azurerm_network_security_group.nsg.id
}

# ── Load Balancer ─────────────────────────────────────────────────────────────
resource "azurerm_public_ip" "lb_pip" {
  name                = "pip-lb-upstream-${var.environment}"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  allocation_method   = "Static"
  sku                 = "Standard"
  zones               = ["1"]
  tags                = local.tags
}

resource "azurerm_lb" "lb" {
  name                = "lb-upstream-${var.environment}"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  sku                 = "Standard"
  tags                = local.tags

  frontend_ip_configuration {
    name                 = "frontend-upstream"
    public_ip_address_id = azurerm_public_ip.lb_pip.id
  }
}

resource "azurerm_lb_backend_address_pool" "backend_pool" {
  loadbalancer_id = azurerm_lb.lb.id
  name            = "backend-upstream"
}

resource "azurerm_lb_probe" "health_probe" {
  loadbalancer_id     = azurerm_lb.lb.id
  name                = "probe-streamlit"
  protocol            = "Tcp"
  port                = 8501
  interval_in_seconds = 15
  number_of_probes    = 2
}

resource "azurerm_lb_rule" "lb_rule_http" {
  loadbalancer_id                = azurerm_lb.lb.id
  name                           = "rule-http-to-streamlit"
  protocol                       = "Tcp"
  frontend_port                  = 80
  backend_port                   = 8501
  frontend_ip_configuration_name = "frontend-upstream"
  backend_address_pool_ids       = [azurerm_lb_backend_address_pool.backend_pool.id]
  probe_id                       = azurerm_lb_probe.health_probe.id
  enable_tcp_reset               = true
  idle_timeout_in_minutes        = 5
}

# ── VM Public IPs (for SSH deployment via GitHub Actions) ─────────────────────
resource "azurerm_public_ip" "vm_pip" {
  count               = 2
  name                = "pip-vm${count.index + 1}-upstream-${var.environment}"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  allocation_method   = "Static"
  sku                 = "Standard"
  zones               = ["1"]
  tags                = local.tags
}

# ── Network Interfaces ────────────────────────────────────────────────────────
resource "azurerm_network_interface" "vm_nic" {
  count               = 2
  name                = "nic-vm${count.index + 1}-upstream-${var.environment}"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  tags                = local.tags

  ip_configuration {
    name                          = "ipconfig1"
    subnet_id                     = azurerm_subnet.app_subnet.id
    private_ip_address_allocation = "Dynamic"
    public_ip_address_id          = azurerm_public_ip.vm_pip[count.index].id
  }
}

# Associate NICs with the LB backend pool
resource "azurerm_network_interface_backend_address_pool_association" "nic_lb_assoc" {
  count                   = 2
  network_interface_id    = azurerm_network_interface.vm_nic[count.index].id
  ip_configuration_name   = "ipconfig1"
  backend_address_pool_id = azurerm_lb_backend_address_pool.backend_pool.id
}

# ── Availability Set (both VMs in Zone 1, fault domains separated) ────────────
resource "azurerm_availability_set" "avset" {
  name                         = "avset-upstream-${var.environment}"
  location                     = azurerm_resource_group.rg.location
  resource_group_name          = azurerm_resource_group.rg.name
  platform_fault_domain_count  = 2
  platform_update_domain_count = 2
  managed                      = true
  tags                         = local.tags
}

# ── Virtual Machines ──────────────────────────────────────────────────────────
resource "azurerm_linux_virtual_machine" "vm" {
  count               = 2
  name                = "vm-upstream-${var.environment}-${count.index + 1}"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  size                = var.vm_size
  availability_set_id = azurerm_availability_set.avset.id
  admin_username      = var.vm_admin_username
  tags                = local.tags

  network_interface_ids = [
    azurerm_network_interface.vm_nic[count.index].id,
  ]

  admin_ssh_key {
    username   = var.vm_admin_username
    public_key = var.ssh_public_key
  }

  os_disk {
    name                 = "osdisk-vm${count.index + 1}-upstream-${var.environment}"
    caching              = "ReadWrite"
    storage_account_type = "Premium_LRS"
    disk_size_gb         = 30
  }

  source_image_reference {
    publisher = "Canonical"
    offer     = "0001-com-ubuntu-server-jammy"
    sku       = "22_04-lts-gen2"
    version   = "latest"
  }

  # Cloud-init bootstraps Python, nginx, systemd service on first boot
  custom_data = base64encode(file("${path.module}/../scripts/cloud_init.sh"))
}

# ── Locals ────────────────────────────────────────────────────────────────────
locals {
  tags = {
    environment = var.environment
    project     = "upstream-data-uploader"
    managed_by  = "terraform"
  }
}
