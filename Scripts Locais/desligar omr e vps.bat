@echo off
echo INICIO DO DESLIGAMENTO
@echo on
taskkill /F /IM Battle.net.exe
taskkill /F /IM BvSsh.exe
timeout 2
"C:\Program Files\Oracle\VirtualBox\VBoxManage.exe" controlvm "OpenMPTCP_OCI" acpipowerbutton
"C:\Program Files\Oracle\VirtualBox\VBoxManage.exe" controlvm "OpenMPTCP" acpipowerbutton
@echo OFF
echo DESLIGAR VPS VPN
echo DESLIGAR VPS JOGO
start /B "" "J:\Dropbox Compartilhado\AmazonWS\Azure Debian 5.4 us-central\Iniciar, desligar instance\Desligar_uscentral_azure.bat"
start /B "" "J:\Dropbox Compartilhado\AmazonWS\Azure Debian 5.4 br-sp\Iniciar, desligar instance\Desligar_br-sp_azure.bat"
@echo ON
timeout 5
taskkill /F /IM sexec.exe
@echo off
echo FIM DO SCRIPT
echo DESLIGAR WINDOWS