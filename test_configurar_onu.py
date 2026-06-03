import pytest
from unittest.mock import patch
from configurar_onu import validar_ip_dispositivo, validar_firmware

class TestValidacaoIP:
    
    def test_ip_invalido_zerado(self):
        ips_vistos = set()
        alerta, msg = validar_ip_dispositivo("0.0.0.0", "PC-Admin", "AA:BB:CC", "192.168.1.2", "192.168.1.254", "255.255.255.0", ips_vistos)
        assert "[!] IP INVÁLIDO" in alerta
        assert "não está navegando" in msg
        assert "PC-Admin" in msg

    def test_ip_invalido_broadcast(self):
        ips_vistos = set()
        alerta, msg = validar_ip_dispositivo("255.255.255.255", "Celular", "11:22:33", "192.168.1.2", "192.168.1.254", "255.255.255.0", ips_vistos)
        assert "[!] IP INVÁLIDO" in alerta
        assert "não está navegando" in msg

    def test_ip_fora_da_subrede(self):
        # A rede correta seria 192.168.1.0/24, mas o IP é 192.168.2.25
        ips_vistos = set()
        alerta, msg = validar_ip_dispositivo("192.168.2.25", "TV", "CC:DD:EE", "192.168.1.2", "192.168.1.254", "255.255.255.0", ips_vistos)
        assert "[!] FORA DA SUB-REDE" in alerta
        assert "fora da rede do roteador" in msg

    def test_ip_estatico_fora_do_range_dhcp(self):
        # A sub-rede tá certa (192.168.1.x), mas o DHCP só dá IP do .10 ao .254. O aparelho está no .5.
        ips_vistos = set()
        alerta, msg = validar_ip_dispositivo("192.168.1.5", "DVR", "FF:AA:11", "192.168.1.10", "192.168.1.254", "255.255.255.0", ips_vistos)
        assert "[IP Estático Fora do Range]" in alerta
        assert "fora do Range DHCP" in msg

    def test_ip_duplicado(self):
        # Simula que o IP já foi visto em outro aparelho
        ips_vistos = {"192.168.1.10"}
        alerta, msg = validar_ip_dispositivo("192.168.1.10", "Smartphone-Clone", "99:88:77", "192.168.1.2", "192.168.1.254", "255.255.255.0", ips_vistos)
        assert "[!] IP DUPLICADO" in alerta
        assert "em uso por mais de um dispositivo" in msg

    def test_ip_duplicado_f680_dict(self):
        # F680 usa um dicionário para rastrear os MACs amarrados aos IPs
        ips_vistos = {"192.168.1.20": "aa:bb:cc:dd:ee:ff"}
        alerta, msg = validar_ip_dispositivo("192.168.1.20", "Novo-Aparelho", "11:22:33:44:55:66", "192.168.1.2", "192.168.1.254", "255.255.255.0", ips_vistos)
        assert "[!] IP DUPLICADO" in alerta
        assert "CONFLITO DE IP DETECTADO" in msg

    def test_ip_valido(self):
        # IP dentro da rede e dentro do range
        ips_vistos = set()
        alerta, msg = validar_ip_dispositivo("192.168.1.50", "Notebook", "55:44:33", "192.168.1.2", "192.168.1.254", "255.255.255.0", ips_vistos)
        assert alerta == ""
        assert msg == ""
        assert "192.168.1.50" in ips_vistos


class TestValidacaoFirmware:

    @patch('os.path.exists')
    @patch('os.listdir')
    @patch('builtins.print')
    def test_firmware_homologado_f6600(self, mock_print, mock_listdir, mock_exists):
        mock_exists.return_value = True
        mock_listdir.return_value = ["F6600P_V9.0.10P6N34 (1).bin"]
        
        validar_firmware("V9.0.10P6N34", "6600")
        
        mock_print.assert_called_with("    [+] Firmware homologado (Arquivo atualizado encontrado na pasta)")

    @patch('os.path.exists')
    @patch('os.listdir')
    @patch('builtins.print')
    def test_firmware_desatualizado_f680(self, mock_print, mock_listdir, mock_exists):
        mock_exists.return_value = True
        mock_listdir.return_value = ["F680_V6.0.10P3N28.bin"]
        
        # O ONU está com a versão P3N9, mais velha
        validar_firmware("V6.0.10P3N9", "680")
        
        # Pega todas as chamadas de print
        calls = [call[0][0] for call in mock_print.call_args_list]
        
        assert any("possivelmente desatualizado" in c for c in calls)
        assert any("F680_V6.0.10P3N28.bin" in c for c in calls)
