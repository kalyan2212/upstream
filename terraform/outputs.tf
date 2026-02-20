output "lb_public_ip" {
  description = "Public IP of the Load Balancer — use this to access the app"
  value       = azurerm_public_ip.lb_pip.ip_address
}

output "vm1_public_ip" {
  description = "Public IP of VM 1 (used by GitHub Actions for SSH deployment)"
  value       = azurerm_public_ip.vm_pip[0].ip_address
}

output "vm2_public_ip" {
  description = "Public IP of VM 2 (used by GitHub Actions for SSH deployment)"
  value       = azurerm_public_ip.vm_pip[1].ip_address
}

output "resource_group_name" {
  description = "Resource Group name"
  value       = azurerm_resource_group.rg.name
}

output "app_url" {
  description = "URL to access the Upstream Data Uploader"
  value       = "http://${azurerm_public_ip.lb_pip.ip_address}"
}
