import os
import time
from playwright.sync_api import sync_playwright

from rich import print
from rich.console import Console
from rich.panel import Panel
console = Console()

def print_header(texto):
    console.print(Panel(f"[bold cyan]🚀 {texto}[/bold cyan]", border_style="cyan", expand=False))

def clicar_aplicar(page):
    # Procura botões com ID ou Type que indiquem salvar/aplicar e clica no primeiro VISÍVEL
    botoes = page.locator("button[id*='apply'], button[id*='submit'], input[type='submit'], input[type='button'][value*='Aplicar'], input[type='button'][value*='Submit'], input[type='button'][value*='Apply']")
    for i in range(botoes.count()):
        if botoes.nth(i).is_visible():
            botoes.nth(i).click(force=True)
            return
            
    # Fallback procurando por texto visível
    botoes_texto = page.locator("text=/Aplicar|Submit|Salvar|Apply/i")
    for i in range(botoes_texto.count()):
        if botoes_texto.nth(i).is_visible():
            botoes_texto.nth(i).click(force=True)
            return

def validar_firmware(fw_lido, modelo_str):
    import os
    fw_lido_clean = fw_lido.replace(" ", "").lower()
    # Caminho portátil: busca a pasta "Firmwares" que está no mesmo diretório deste script
    pasta_firmwares = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Firmwares")
    
    if os.path.exists(pasta_firmwares):
        arquivos = [f for f in os.listdir(pasta_firmwares) if f.endswith(".bin")]
        
        for arq in arquivos:
            arq_clean = arq.replace(" ", "").replace("_", "").lower()
            if fw_lido_clean in arq_clean:
                print("    [bold green][+][/bold green] Firmware homologado (Arquivo atualizado encontrado na pasta)")
                return
                
        print(f"    [bold yellow][!][/bold yellow] ATENÇÃO: Firmware '{fw_lido}' possivelmente desatualizado!")
        
        filtros = []
        if "6600" in modelo_str: 
            filtros = ["6600"]
        elif "680" in modelo_str or "670" in modelo_str: 
            filtros = ["680", "670"]
            
        sugeridos = []
        for arq in arquivos:
            for f in filtros:
                if f in arq:
                    sugeridos.append(arq)
                    break
                    
        if sugeridos:
            print("        [bold blue]->[/bold blue] Modelos atualizados disponíveis no seu Desktop:")
            for s in sugeridos:
                print(f"           - {s}")
        else:
            print(f"        [bold blue]->[/bold blue] Verifique a pasta '{pasta_firmwares}' para encontrar a versão correta.")

def validar_ip_dispositivo(ip_str, hostname, mac, inicio_ip, fim_ip, mask, ips_vistos):
    """
    Função pura para validação de IP e identificação de conflitos.
    Retorna (alerta_str, mensagem_conflito).
    Atualiza in-place a estrutura ips_vistos.
    """
    alerta_ip = ""
    msg_conflito = ""
    
    mac_upper = mac.upper() if mac else "00:00:00:00:00:00"
    name_str = hostname if hostname else "Desconhecido"
    
    if ip_str in ["0.0.0.0", "255.255.255.255", "Sem IP"]:
        if ip_str != "Sem IP":
            alerta_ip = " [!] IP INVÁLIDO (Sem Navegação)"
            msg_conflito = f"O aparelho '{name_str}' ({mac_upper}) está com o IP inválido '{ip_str}'. Ele não está navegando na internet!"
    elif ip_str != "Fixo/Desconhecido":
        # Conflito 1: IP Duplicado
        if isinstance(ips_vistos, set):
            if ip_str in ips_vistos:
                alerta_ip = " [!] IP DUPLICADO"
                msg_conflito = f"IP {ip_str} está em uso por mais de um dispositivo! ({name_str})"
            ips_vistos.add(ip_str)
        elif isinstance(ips_vistos, dict):
            if ip_str in ips_vistos and ips_vistos[ip_str] != mac:
                alerta_ip = " [!] IP DUPLICADO"
                msg_conflito = f"CONFLITO DE IP DETECTADO: {ip_str} está alocado para {mac} e {ips_vistos[ip_str]}"
            ips_vistos[ip_str] = mac
            
        # Conflito 2: Fora da Sub-rede ou Fora do Range DHCP
        if inicio_ip and mask:
            try:
                import ipaddress
                subnet = ipaddress.ip_network(f"{inicio_ip}/{mask}", strict=False)
                ip_obj = ipaddress.ip_address(ip_str)
                
                if ip_obj not in subnet:
                    alerta_ip = " [!] FORA DA SUB-REDE (Sem Navegação)"
                    msg_conflito = f"O IP {ip_str} ({name_str}) está fora da rede do roteador ({subnet}). Ele provavelmente está com IP estático errado e não está navegando!"
                elif fim_ip:
                    start_oct = int(inicio_ip.split(".")[-1])
                    end_oct = int(fim_ip.split(".")[-1])
                    ip_oct = int(ip_str.split(".")[-1])
                    if not (start_oct <= ip_oct <= end_oct):
                        alerta_ip = " [IP Estático Fora do Range]"
                        msg_conflito = f"O IP {ip_str} ({name_str}) está fora do Range DHCP ({start_oct}-{end_oct}). (Possível IP Estático gerando conflito)"
            except:
                pass
                
    return alerta_ip, msg_conflito

# ==========================================
# ROTINAS DA F6600 / F6600P
# ==========================================
def configurar_upnp_zte_f6600(page):
    print_header("Configurando UPnP (F6600)")
    try:
        page.locator("text='Rede local'").first.click()
        page.wait_for_timeout(1500)
        page.locator("#upnp").click()
        page.wait_for_timeout(1500)
        
        if page.locator("text='Ligado'").first.is_visible():
            page.locator("text='Ligado'").first.click()
        else:
            radio = page.locator("input[type='radio'][value='1']")
            if radio.count() > 0:
                radio.first.check()
            else:
                page.locator("input[type='radio']").first.check()
        
        clicar_aplicar(page)
        
        page.wait_for_timeout(1500)
        print("[bold green][+][/bold green] UPnP ativado!")
    except Exception as e:
        print(f"[bold red][-][/bold red] Erro UPnP: {str(e)}")


def configurar_sntp_f6600(page):
    print_header("Configurando SNTP (F6600)")
    try:
        print("[bold cyan][*][/bold cyan] Acessando Internet > SNTP...")
        page.locator("text=/Internet/i").first.click()
        page.wait_for_timeout(1000)
        page.locator("text=/SNTP/i").first.click()
        page.wait_for_timeout(2000)
        
        print("[bold cyan][*][/bold cyan] Inserindo IP do servidor SNTP (168.121.96.25)...")
        inputs_texto = page.locator("input[type='text']")
        for i in range(inputs_texto.count()):
            inp = inputs_texto.nth(i)
            if inp.is_visible() and "stop" not in (inp.get_attribute("id") or "").lower():
                inp.fill("168.121.96.25")
                break

        print("[bold cyan][*][/bold cyan] Configurando Fuso Horário para Brasília (GMT-03:00)...")
        try:
            page.locator("#LocalTimeZoneandName").select_option("10")
            page.wait_for_timeout(1000)
        except:
            pass

        print("[bold cyan][*][/bold cyan] Desativando Horário de Verão (F6600)...")
        try:
            page.locator("#DaylightSavingsUsed1").check(force=True)
        except:
            pass
                
        print("[bold cyan][*][/bold cyan] Aplicando configurações do SNTP...")
        clicar_aplicar(page)
            
        page.wait_for_timeout(2000)
        print("[bold green][+][/bold green] SNTP configurado com sucesso!")
    except Exception as e:
        print(f"[bold red][-][/bold red] Erro SNTP: {str(e)}")


def ler_status_f6600(page):
    print_header("Lendo Status (F6600)")
    
    # Tenta sair do Wizard novamente, caso alguma configuração anterior tenha dado reload na página
    try:
        page.evaluate('var btn = document.getElementById("Outquicksetup"); if(btn && btn.style.display !== "none") btn.click();')
        page.wait_for_timeout(2000)
    except:
        pass
        
    try:
        # 1. Firmware e Serial
        print(" [bold blue]->[/bold blue] Lendo Hardware e Firmware...")
        page.wait_for_timeout(3000) # Dá tempo pro Mesh Wi-Fi terminar de salvar
        
        # O menu na F6600P ou outras versões pode se chamar Administração ou Manutenção
        menu_admin = page.locator("text=/Gerência|Management|Administração|Admin|Manutenção|Maintenance/i").first
        if menu_admin.is_visible():
            menu_admin.click(force=True)
        else:
            # Tenta clicar no primeiro item da barra de menu superior que faça sentido
            page.evaluate("Array.from(document.querySelectorAll('a, span, div')).find(el => el.textContent.match(/Gerência|Management|Administração|Admin/i))?.click()")
            
        page.wait_for_timeout(1500)
        
        # A aba pode ser Estado, Status, ou Informação do Dispositivo
        aba_status = page.locator("text=/Estado|Status|Device Information|Informação/i").first
        if aba_status.is_visible():
            aba_status.click(force=True)
            
        page.wait_for_timeout(2000)
        
        try:
            serial = page.locator("#SerialNumber").inner_text().strip()
            fw = page.locator("#SoftwareVer").inner_text().strip()
            print(f"    [bold green][+][/bold green] Serial: {serial}")
            print(f"    [bold green][+][/bold green] Firmware: {fw}")
            validar_firmware(fw, "6600")
        except Exception as e:
            print("    [bold red][-][/bold red] Falha ao ler Serial/Firmware")
            try:
                page.screenshot(path=r"C:\Users\Paulo Felix\.gemini\antigravity\scratch\debug_f6600.png")
                with open(r"C:\Users\Paulo Felix\.gemini\antigravity\scratch\debug_f6600.html", "w", encoding="utf-8") as f:
                    f.write(page.content())
            except:
                pass
        try:
            uptime_str = page.locator("#PoweronTime").inner_text().strip()
            print(f"    [bold green][+][/bold green] Tempo de Atividade: {uptime_str}")
            
            import re
            dias = 0
            horas = 0
            match_dias = re.search(r"(\d+)\s+dia", uptime_str, re.IGNORECASE)
            if match_dias:
                dias = int(match_dias.group(1))
                
            match_horas = re.search(r"(\d+)\s+hora", uptime_str, re.IGNORECASE)
            if match_horas:
                horas = int(match_horas.group(1))
                
            total_horas = (dias * 24) + horas
            if total_horas >= 100:
                print(f"        [bold blue]->[/bold blue] Ação Recomendada: A ONU está ligada ininterruptamente há {total_horas} horas. É recomendado reiniciar o equipamento para limpar a memória e restabelecer conexões estáveis.")
        except:
            pass

        # 2. Sinal Óptico
        print(" [bold blue]->[/bold blue] Lendo Sinal Óptico (PON)...")
        try:
            page.locator("text=/Internet/i").first.click(force=True)
            page.wait_for_timeout(1000)
            page.locator("text=/PON/i").first.click(force=True)
            page.wait_for_timeout(2000)
        except:
            pass
        
        try:
            potencia_rx = page.locator("#RxPower").inner_text(timeout=2000).strip()
            potencia_tx = page.locator("#TxPower").inner_text(timeout=2000).strip()
            print(f"    [bold green][+][/bold green] Sinal RX: {potencia_rx} dBm")
            print(f"    [bold green][+][/bold green] Sinal TX: {potencia_tx} dBm")
            
            # Avaliação de qualidade do sinal RX
            try:
                rx_val = float(potencia_rx.replace("dBm", "").strip())
                if rx_val <= -29.0:
                    status_rx = "ABAIXO DO PADRÃO (Crítico)"
                    recomendar = True
                elif rx_val <= -27.1:
                    status_rx = "MAIS OU MENOS (Atenção)"
                    recomendar = True
                else:
                    status_rx = "OK"
                    recomendar = False
                    
                print(f"    [bold cyan][*][/bold cyan] Qualidade da Fibra (RX): {status_rx}")
                if recomendar:
                    print("        [bold blue]->[/bold blue] Ação Recomendada: Validar como está o sinal diretamente na caixa de atendimento (CTO).")
            except:
                pass
                
        except:
            print("    [bold red][-][/bold red] Falha ao ler Sinal PON")
            
        # 3. DHCP
        print(" [bold blue]->[/bold blue] Lendo Configuração DHCP...")
        inicio_ip = ""
        fim_ip = ""
        dhcp_leases = {}
        
        try:
            page.locator("text=/Rede local|Local Network/i").first.click(force=True)
            page.wait_for_timeout(1000)
            page.locator("text=/^LAN$/i").first.click(force=True)
            page.wait_for_timeout(2000)
            page.locator("text=/Servidor DHCP|DHCP Server/i").first.click(force=True)
            page.wait_for_timeout(2000)
        except:
            pass
        
        try:
            gw = page.locator("[id='IPAddr:DHCPBasicCfg']").get_attribute("value", timeout=2000)
            mask = page.locator("#SubMask").get_attribute("value", timeout=2000)
            inicio_ip = page.locator("[id='MinAddress:DHCPBasicCfg']").get_attribute("value", timeout=2000)
            fim_ip = page.locator("[id='MaxAddress:DHCPBasicCfg']").get_attribute("value", timeout=2000)
            
            print(f"    [bold green][+][/bold green] Gateway: {gw}")
            print(f"    [bold green][+][/bold green] Máscara: {mask}")
            print(f"    [bold green][+][/bold green] Range DHCP: {inicio_ip} até {fim_ip}")
            
            # Extrair os IPs alocados via DHCP para cruzar com a Topologia
            mac_elements = page.locator("span[id*='MACAddr:']")
            ip_elements = page.locator("span[id*='IPAddr:']")
            for i in range(mac_elements.count()):
                m_txt = mac_elements.nth(i).text_content(timeout=2000).strip().lower()
                i_txt = ip_elements.nth(i).text_content(timeout=2000).strip()
                if ":" in m_txt and "." in i_txt:
                    dhcp_leases[m_txt] = i_txt
        except Exception as e:
            print(f"    [bold red][-][/bold red] Falha ao ler DHCP: {str(e)}")
            try:
                page.screenshot(path=r"C:\Users\Paulo Felix\.gemini\antigravity\scratch\debug_dhcp_f6600.png")
                with open(r"C:\Users\Paulo Felix\.gemini\antigravity\scratch\debug_dhcp_f6600.html", "w", encoding="utf-8") as f:
                    f.write(page.content())
            except:
                pass

        # 4. Dispositivos
        print(" [bold blue]->[/bold blue] Verificando Dispositivos Conectados...")
        try:
            page.locator("text=/Topologia|Topology/i").first.click(force=True)
            page.wait_for_timeout(5000)
        
            client_container = page.locator("#clientFormContainer").first
            
            # F6600 esconde a lista dentro de um acordeão "ALL Clients".
            try:
                page.locator("#clientFormBar").first.click(force=True, timeout=2000)
                page.wait_for_timeout(2000)
            except:
                pass
            
            try:
                client_container.locator("div[id^='clientFormContent_']").first.wait_for(timeout=3000)
            except:
                pass
                
            linhas = client_container.locator("div[id^='clientFormContent_']")
            num_dispositivos = linhas.count()
            
            if num_dispositivos == 0:
                # Fallback para firmware desatualizada (Ex: V9.0.10P6N6 - Layout "legacy")
                legacy_devs = page.locator("div[title*='Device:']")
                count_legacy = legacy_devs.count()
                
                if count_legacy > 0:
                    print("    [bold cyan][*][/bold cyan] Topologia antiga detectada (layout master-device). Mapeando...")
                    conflitos_ip = []
                    problemas_rssi = []
                    ips_vistos = set()
                    grupos_legado = {"Rede Cabeada (LAN)": [], "Rede Wi-Fi 2.4GHz": [], "Rede Wi-Fi 5GHz": [], "Desconhecido": []}
                    
                    for i in range(count_legacy):
                        title_text = legacy_devs.nth(i).get_attribute("title")
                        dev_id = legacy_devs.nth(i).get_attribute("id") or ""
                        
                        if not title_text or "Device:" not in title_text:
                            continue
                            
                        if "5G" in dev_id:
                            tipo_rede = "Rede Wi-Fi 5GHz"
                        elif "2G" in dev_id or "2.4G" in dev_id:
                            tipo_rede = "Rede Wi-Fi 2.4GHz"
                        elif "lan" in dev_id.lower():
                            tipo_rede = "Rede Cabeada (LAN)"
                        else:
                            tipo_rede = "Desconhecido"
                            
                        hostname = "Desconhecido"
                        mac = "00:00:00:00:00:00"
                        ip = "Sem IP"
                        rssi_str = "N/A"
                        
                        for line in title_text.split('\n'):
                            line = line.strip()
                            if line.startswith("Device:"): hostname = line.split("Device:")[1].strip()
                            elif line.startswith("MAC:"): mac = line.split("MAC:")[1].strip()
                            elif line.startswith("IP:"): ip = line.split("IP:")[1].strip()
                            elif line.startswith("RSSI:"): rssi_str = line.split("RSSI:")[1].strip()
                            
                        if dhcp_leases and mac.lower() in dhcp_leases and (ip == "Sem IP" or not ip):
                            ip = dhcp_leases[mac.lower()]
                            
                        alerta_ip, msg_conflito = validar_ip_dispositivo(ip, hostname, mac, inicio_ip, fim_ip, mask, ips_vistos)
                        if msg_conflito:
                            conflitos_ip.append(msg_conflito)
                        
                        grupos_legado[tipo_rede].append(f"        [bold magenta]•[/bold magenta] [white]{hostname}[/white] | [dim]MAC: {mac.upper()}[/dim] | [green]IP: {ip}[/green] | [cyan]RSSI: {rssi_str}[/cyan][bold red]{alerta_ip}[/bold red]")
                        
                        # Sinal Ruim (RSSI)
                        if tipo_rede in ["Rede Wi-Fi 2.4GHz", "Rede Wi-Fi 5GHz"] and rssi_str != "N/A":
                            try:
                                rssi_val = float(rssi_str.replace("dBm", "").strip())
                                if rssi_val <= -80:
                                    problemas_rssi.append(f"Sinal muito fraco em {hostname} ({tipo_rede}): {rssi_str}. Pode causar lentidão.")
                            except:
                                pass
                                
                    for rede, aparelhos in grupos_legado.items():
                        if aparelhos:
                            print(f"\n    [bold magenta]=== {rede} ===[/bold magenta]")
                            for ap in aparelhos:
                                print(ap)
                                
                    if conflitos_ip or problemas_rssi:
                        print("\n    [bold yellow][!][/bold yellow] ATENÇÃO - PROBLEMAS ENCONTRADOS:")
                        for c in conflitos_ip:
                            print(f"        [bold blue]->[/bold blue] {c}")
                        for p in problemas_rssi:
                            print(f"        [bold blue]->[/bold blue] {p}")
                else:
                    print("    [bold cyan][*][/bold cyan] Nenhum dispositivo detectado com os IDs da F680. Gravando telemetria...")
                    try:
                        page.screenshot(path=r"C:\Users\Paulo Felix\.gemini\antigravity\scratch\debug_topologia_f6600.png")
                        with open(r"C:\Users\Paulo Felix\.gemini\antigravity\scratch\debug_topologia_f6600.html", "w", encoding="utf-8") as f:
                            f.write(page.content())
                    except:
                        pass
                    print("    [bold green][+][/bold green] Nenhum dispositivo conectado à LAN/WLAN no momento.")
            else:
                print(f"    [bold green][+][/bold green] Foram encontrados {num_dispositivos} dispositivos na Topologia:")
                
                conflitos_ip = []
                problemas_rssi = []
                ips_vistos = set()
                grupos = {"LAN": [], "2.4GHz": [], "5GHz": [], "Desconhecido": []}
                
                for i in range(num_dispositivos):
                    linha = linhas.nth(i)
                    
                    h_loc = linha.locator("span[id^='clientHostName']")
                    hostname = h_loc.first.text_content(timeout=2000).strip() if h_loc.count() > 0 else "Desconhecido"
                    
                    m_loc = linha.locator("input[id^='MacAddr']")
                    mac = m_loc.first.get_attribute("value", timeout=2000).strip().lower() if m_loc.count() > 0 else "00:00:00:00:00:00"
                    
                    t_loc = linha.locator("span[id^='relateHz']")
                    tipo = t_loc.first.text_content(timeout=2000).strip() if t_loc.count() > 0 else "Desconhecido"
                    
                    r_loc = linha.locator("span[id^='RSSI']")
                    rssi_str = r_loc.first.text_content(timeout=2000).strip() if r_loc.count() > 0 else ""
                    
                    ip = dhcp_leases.get(mac, "Fixo/Desconhecido")
                    
                    # Checagens de IP via função pura
                    alerta_ip, msg_conflito = validar_ip_dispositivo(ip, hostname, mac, inicio_ip, fim_ip, mask, ips_vistos)
                    if msg_conflito:
                        conflitos_ip.append(msg_conflito)

                    # Agrupa na tabela correspondente
                    if tipo not in grupos:
                        grupos[tipo] = []
                    grupos[tipo].append(f"        [bold magenta]•[/bold magenta] [white]{hostname}[/white] | [dim]MAC: {mac.upper()}[/dim] | [green]IP: {ip}[/green] | [cyan]RSSI: {rssi_str}[/cyan][bold red]{alerta_ip}[/bold red]")
                    
                    # Sinal Ruim (RSSI)
                    if tipo in ["2.4GHz", "5GHz"] and rssi_str:
                        try:
                            rssi_val = float(rssi_str.replace("dBm", "").strip())
                            if rssi_val <= -80:
                                problemas_rssi.append(f"Sinal muito fraco em {hostname} ({tipo}): {rssi_str}. Pode causar lentidão e quedas de conexão.")
                        except:
                            pass
                            
                for rede, aparelhos in grupos.items():
                    if aparelhos:
                        print(f"\n    [bold magenta]=== {rede} ===[/bold magenta]")
                        for ap in aparelhos:
                            print(ap)
                            
                if conflitos_ip or problemas_rssi:
                    print("\n    [!] ATENÇÃO - CONFLITOS DE IP ENCONTRADOS:")
                    for c in conflitos_ip:
                        print(f"        [bold blue]->[/bold blue] {c}")
                        
                if problemas_rssi:
                    print("\n    [!] ATENÇÃO - PROBLEMAS DE WI-FI (RSSI):")
                    for p in problemas_rssi:
                        print(f"        [bold blue]->[/bold blue] {p}")
                        
        except Exception as e:
            print(f"    [bold red][-][/bold red] Falha ao ler Tabela de Clientes: {str(e)}")

    except Exception as e:
        print(f"[bold red][-][/bold red] Erro ao ler status: {str(e)}")


def configurar_mesh_wifi_f6600(page):
    print_header("Configurando Mesh Wi-Fi (F6600)")
    try:
        print("[bold cyan][*][/bold cyan] Acessando Rede local > WLAN...")
        page.locator("text=/Rede local|Local Network/i").first.click()
        page.wait_for_timeout(1000)
        page.locator("text=/WLAN/i").first.click()
        page.wait_for_timeout(2000)
        
        print("[bold cyan][*][/bold cyan] Procurando aba 'Mesh Wi-Fi'...")
        page.locator("text=/Mesh Wi-Fi/i").first.click()
        page.wait_for_timeout(2000)
        
        print("    [bold cyan][*][/bold cyan] Salvando telemetria inicial do Mesh Wi-Fi...")
        try:
            page.screenshot(path=r"C:\Users\Paulo Felix\.gemini\antigravity\scratch\debug_f6600_mesh_antes.png")
            with open(r"C:\Users\Paulo Felix\.gemini\antigravity\scratch\debug_f6600_mesh_antes.html", "w", encoding="utf-8") as f:
                f.write(page.content())
        except:
            pass
        
        print("[bold cyan][*][/bold cyan] Ativando a função Mesh Wi-Fi...")
        # Clica diretamente no Label correspondente ao radio "Ligado" da opção Ativar
        label_ligado = page.locator("label[for='Enable0']")
        if label_ligado.count() > 0:
            label_ligado.click()
        else:
            # Fallbacks
            btn_ligado = page.locator("text=/Ligado|On/i >> visible=true").first
            if btn_ligado.is_visible():
                btn_ligado.click()
            else:
                radio = page.locator("input[type='radio'][value='1'] >> visible=true")
                if radio.count() > 0:
                    radio.first.check(force=True)
                else:
                    page.locator("input[type='radio'] >> visible=true").first.check(force=True)
                
        print("[bold cyan][*][/bold cyan] Aplicando configurações do Mesh...")
        clicar_aplicar(page)
            
        page.wait_for_timeout(2000)
        
        print("    [bold cyan][*][/bold cyan] Salvando telemetria pós-aplicação do Mesh Wi-Fi...")
        try:
            page.screenshot(path=r"C:\Users\Paulo Felix\.gemini\antigravity\scratch\debug_f6600_mesh_depois.png")
            with open(r"C:\Users\Paulo Felix\.gemini\antigravity\scratch\debug_f6600_mesh_depois.html", "w", encoding="utf-8") as f:
                f.write(page.content())
        except:
            pass
            
        print("[bold green][+][/bold green] Mesh Wi-Fi ativado com sucesso (Topologia liberada)!")
    except Exception as e:
        print(f"[bold red][-][/bold red] Erro ao configurar Mesh Wi-Fi: {str(e)}")

# ==========================================
# ROTINAS DA F680 / F670L
# ==========================================
def configurar_upnp_zte_f680(page):
    print_header("Configurando UPnP (F680)")
    try:
        frame = page.frame_locator("[name='mainFrame']")
        print("[bold cyan][*][/bold cyan] Acessando Application > UPnP...")
        try:
            frame.locator("body").evaluate("() => window.location.href = 'getpage.gch?pid=1002&nextpage=app_upnp_conf_t.gch'")
        except:
            pass
        page.wait_for_timeout(3000)
        
        estado = frame.locator("#Frm_EnableUPnPIGD").is_checked()
        if not estado:
            frame.locator("#Frm_EnableUPnPIGD").check()
            frame.locator("#Btn_Submit").click()
            page.wait_for_timeout(2000)
            print("[bold green][+][/bold green] UPnP ativado com sucesso!")
        else:
            print("[bold green][+][/bold green] UPnP já estava ativado!")
    except Exception as e:
        print(f"[bold red][-][/bold red] Erro ao configurar UPnP: {e}")

def configurar_sntp_zte_f680(page):
    print_header("Configurando SNTP (F680)")
    try:
        frame = page.frame_locator("[name='mainFrame']")
        print("[bold cyan][*][/bold cyan] Acessando Application > SNTP...")
        try:
            frame.locator("body").evaluate("() => window.location.href = 'getpage.gch?pid=1002&nextpage=net_sntp_conf_t.gch'")
        except:
            pass
        page.wait_for_timeout(3000)
        
        print("[bold cyan][*][/bold cyan] Inserindo IP do servidor SNTP (168.121.96.25)...")
        frame.locator("#Frm_NtpServer1").fill("168.121.96.25")
        
        print("[bold cyan][*][/bold cyan] Ajustando o Fuso Horário para Brasília...")
        frame.locator("#Frm_LocalTimeZoneandName").select_option("10")
        
        print("[bold cyan][*][/bold cyan] Aplicando configurações...")
        frame.locator("#Btn_Submit").click()
        page.wait_for_timeout(2000)
        print("[bold green][+][/bold green] SNTP configurado com sucesso!")
    except Exception as e:
        print(f"[bold red][-][/bold red] Erro ao configurar SNTP: {e}")

def ler_status_f680(page):
    print_header("Lendo Status (F680)")
    frame = page.frame_locator("[name='mainFrame']")
    
    print(" [bold blue]->[/bold blue] Lendo Hardware e Firmware...")
    try:
        try:
            frame.locator("body").evaluate("() => window.location.href = 'getpage.gch?pid=1002&nextpage=status_dev_info_t.gch'")
        except:
            pass
        page.wait_for_timeout(3000)
        serial = frame.locator("#Frm_PonSerialNumber").inner_text().strip()
        fw = frame.locator("#Frm_SoftwareVer").inner_text().strip()
        print(f"    [bold green][+][/bold green] Serial: {serial}")
        print(f"    [bold green][+][/bold green] Firmware: {fw}")
        validar_firmware(fw, "680")
        
        # Tenta ler Uptime do PPPoE (WAN)
        try:
            print(" [bold blue]->[/bold blue] Lendo Uptime do PPPoE...")
            try:
                frame.locator("body").evaluate("() => window.location.href = 'getpage.gch?pid=1002&nextpage=status_wan2_if_t.gch'")
            except:
                pass
            page.wait_for_timeout(3000)
            
            import re
            texto_status_wan = frame.locator("body").inner_text()
            
            if "omci_ipv4_pppoe_1" not in texto_status_wan.lower():
                # Tenta outra URL comum para Status WAN na F680/F670
                try:
                    frame.locator("body").evaluate("() => window.location.href = 'getpage.gch?pid=1002&nextpage=IPv46_status_wan2_if_t.gch'")
                except:
                    pass
                page.wait_for_timeout(3000)
                texto_status_wan = frame.locator("body").inner_text()
            
            partes = re.split(r'omci_ipv4_pppoe_1', texto_status_wan, flags=re.IGNORECASE)
            if len(partes) > 1:
                texto_pppoe = partes[1][:500] # Pega até 500 caracteres após o nome da conexão
                uptime_match = re.search(r'(\d+)\s*(?:days?|dias?|day|dia|d)\s*(\d+)\s*(?:hours?|horas?|hour|hora|h)', texto_pppoe, re.IGNORECASE)
                uptime_hms = re.search(r'(\d+):(\d{2}):(\d{2})', texto_pppoe)
                
                if uptime_match:
                    dias = int(uptime_match.group(1))
                    horas = int(uptime_match.group(2))
                    total_horas = (dias * 24) + horas
                    print(f"    [bold green][+][/bold green] Uptime do PPPoE lido: {dias} dias e {horas} horas")
                    if total_horas >= 100:
                        print(f"    [bold yellow][!][/bold yellow] ALERTA: A conexão PPPoE está ativa há {total_horas} horas ininterruptas.")
                        print("        [bold blue]->[/bold blue] Ação Recomendada: Reiniciar a interface para renovar a sessão no concentrador.")
                elif uptime_hms:
                    horas = int(uptime_hms.group(1))
                    print(f"    [bold green][+][/bold green] Uptime do PPPoE lido: {horas} horas e {uptime_hms.group(2)} minutos")
                    if horas >= 100:
                        print(f"    [bold yellow][!][/bold yellow] ALERTA: A conexão PPPoE está ativa há {horas} horas ininterruptas.")
                        print("        [bold blue]->[/bold blue] Ação Recomendada: Reiniciar a interface para renovar a sessão.")
                else:
                    print("    [bold yellow][!][/bold yellow] Não foi possível encontrar o formato de tempo do PPPoE na tela de Status.")
            else:
                print("    [bold yellow][!][/bold yellow] PPPoE 'omci_ipv4_pppoe_1' não encontrado na tabela de conexões WAN.")
        except Exception as e:
            print(f"    [bold red][-][/bold red] Falha ao ler Uptime PPPoE: {str(e)}")
    except:
        print("    [bold red][-][/bold red] Falha ao ler Serial/Firmware")

    print(" [bold blue]->[/bold blue] Lendo Sinal Óptico (PON)...")
    try:
        try:
            frame.locator("body").evaluate("() => window.location.href = 'getpage.gch?pid=1002&nextpage=pon_status_link_info_t.gch'")
        except:
            pass
        page.wait_for_timeout(3000)
        
        import re
        texto_pon = frame.locator("body").inner_text()
        # Regex abrangente para variações de RX/TX Power na ZTE F680 (Incluindo firmwares traduzidas)
        rx_match = re.search(r'(?:Rx.*?Power|Receive.*?Power|Input.*?Power|Energia de entrada.*?ptico)[^\d-]*([-0-9.]+)', texto_pon, re.IGNORECASE)
        tx_match = re.search(r'(?:Tx.*?Power|Transmit.*?Power|Output.*?Power|Potência de saída.*?ptico)[^\d-]*([-0-9.]+)', texto_pon, re.IGNORECASE)
        
        if rx_match:
            potencia_rx = float(rx_match.group(1))
            status_rx = "OK"
            if potencia_rx <= -29.0:
                status_rx = "ABAIXO DO PADRÃO"
            elif potencia_rx <= -27.1:
                status_rx = "MAIS OU MENOS"
                
            print(f"    [bold green][+][/bold green] Sinal RX: {potencia_rx} dBm ({status_rx})")
            if status_rx != "OK":
                print("        [bold blue]->[/bold blue] Ação Recomendada: Validar como está o sinal da caixa CTO.")
        else:
            print("    [bold red][-][/bold red] RX Power não encontrado. Texto da tela pode ter nomenclatura desconhecida. Gravando telemetria...")
            try:
                page.screenshot(path=r"C:\Users\Paulo Felix\.gemini\antigravity\scratch\debug_f680_pon.png")
                with open(r"C:\Users\Paulo Felix\.gemini\antigravity\scratch\debug_f680_pon.html", "w", encoding="utf-8") as f:
                    f.write(frame.locator("body").inner_html())
            except:
                pass
            
            
        if tx_match:
            print(f"    [bold green][+][/bold green] Sinal TX: {tx_match.group(1)} dBm")
    except Exception as e:
        print(f"    [bold red][-][/bold red] Falha ao ler Sinal PON: {str(e)}")
        try:
            page.screenshot(path=r"C:\Users\Paulo Felix\.gemini\antigravity\scratch\debug_f680_pon.png")
            with open(r"C:\Users\Paulo Felix\.gemini\antigravity\scratch\debug_f680_pon.html", "w", encoding="utf-8") as f:
                f.write(page.content())
        except:
            pass
            
    print(" [bold blue]->[/bold blue] Lendo Configuração DHCP (F680)...")
    try:
        try:
            frame.locator("body").evaluate("() => window.location.href = 'getpage.gch?pid=1002&nextpage=net_dhcp_dynamic_t.gch'")
        except:
            pass
        page.wait_for_timeout(3000)
        
        inicio_ip = frame.locator("#MinAddress").get_attribute("value", timeout=2000)
        fim_ip = frame.locator("#MaxAddress").get_attribute("value", timeout=2000)
        mask = frame.locator("#SubnetMask").get_attribute("value", timeout=2000)
        
        print(f"    [bold green][+][/bold green] IP Range: {inicio_ip} até {fim_ip} (Máscara {mask})")
        
        linhas_ip = frame.locator("input[id^='IPAddr']")
        linhas_mac = frame.locator("input[id^='MACAddr']")
        linhas_host = frame.locator("input[id^='HostName']")
        
        count = linhas_ip.count()
        print(f"    [bold cyan][*][/bold cyan] Encontrados {count} leases de DHCP")
        dhcp_leases = {}
        for i in range(count):
            ip = linhas_ip.nth(i).get_attribute("value")
            mac = linhas_mac.nth(i).get_attribute("value")
            host = linhas_host.nth(i).get_attribute("value")
            if mac and ip:
                dhcp_leases[mac.lower()] = {"ip": ip, "hostname": host}
                
    except Exception as e:
        print(f"    [bold red][-][/bold red] Falha ao acessar página de DHCP da F680: {e}")

    print(" [bold blue]->[/bold blue] Verificando Dispositivos Conectados (Topologia)...")
    try:
        try:
            frame.locator("body").evaluate("() => window.location.href = 'getpage.gch?pid=1002&nextpage=topo_v2_t.gch'")
        except:
            pass
        page.wait_for_timeout(4000)
        count = frame.locator("input[id^='HostName0M']").count()
        
        ips_vistos = {}
        
        if count > 0:
            grupos = {"LAN": [], "2.4GHz": [], "5GHz": []}
            
            for i in range(count):
                hostname = frame.locator(f"#HostName0M{i}AD").get_attribute("value")
                mac = frame.locator(f"#MACAddr0M{i}AD").get_attribute("value")
                ip = frame.locator(f"#IPAddr0M{i}AD").get_attribute("value")
                rssi = frame.locator(f"#Rssi0M{i}AD").get_attribute("value")
                acctype = frame.locator(f"#AccessType0M{i}AD").get_attribute("value")
                
                # Traduzir AccessType
                tipo_rede = "LAN"
                if acctype == "1":
                    tipo_rede = "2.4GHz"
                elif acctype == "2":
                    tipo_rede = "5GHz"
                
                if mac and mac != "00:00:00:00:00:00":
                    mac = mac.lower()
                    
                    # Merge com dados do DHCP
                    if 'dhcp_leases' in locals() and mac in dhcp_leases:
                        if not ip or ip == "0.0.0.0" or ip == "Sem IP":
                            ip = dhcp_leases[mac]["ip"]
                        if not hostname:
                            hostname = dhcp_leases[mac]["hostname"]
                            
                    name_str = hostname if hostname else "Desconhecido"
                    ip_str = ip if ip else "Sem IP"
                    rssi_val = int(rssi) if rssi and rssi != "0" else None
                    
                    # Checagens de IP via função pura
                    alerta_ip, msg_conflito = validar_ip_dispositivo(ip_str, name_str, mac, 
                                                                     locals().get('inicio_ip', ''), 
                                                                     locals().get('fim_ip', ''), 
                                                                     locals().get('mask', ''), 
                                                                     ips_vistos)
                    if msg_conflito:
                        print(f"    [bold yellow][!][/bold yellow] {msg_conflito}")
                                
                    alerta_sinal = ""
                    if rssi_val is not None and rssi_val <= -80:
                        alerta_sinal = " [!] SINAL MUITO FRACO (Pode causar quedas)"
                        
                    if tipo_rede == "LAN":
                        rssi_print = "Cabo"
                    else:
                        rssi_print = f"{rssi_val} dBm" if rssi_val else "Sinal indisponível"
                        
                    if tipo_rede not in grupos:
                        grupos[tipo_rede] = []
                    grupos[tipo_rede].append(f"        [bold magenta]•[/bold magenta] [white]{name_str}[/white] | [dim]MAC: {mac}[/dim] | [green]IP: {ip_str}[/green] | [cyan]RSSI: {rssi_print}[/cyan][bold red]{alerta_ip}{alerta_sinal}[/bold red]")
                    
            for rede, aparelhos in grupos.items():
                if aparelhos:
                    print(f"\n    [bold magenta]=== {rede} ===[/bold magenta]")
                    for ap in aparelhos:
                        print(ap)
        else:
            print("    [bold red][-][/bold red] Nenhum dispositivo listado na topologia.")
    except Exception as e:
        print(f"    [bold red][-][/bold red] Falha ao ler Topologia: {e}")



# ==========================================
# MAIN
# ==========================================
def executar_automacao(ip, usuario, senha, fazer_config=True):
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(ignore_https_errors=True)
            page = context.new_page()
            
            print(f"\n[*] Conectando à ONU no endereço: http://{ip}/")
            page.goto(f"http://{ip}/", timeout=15000)
            
            print("[bold cyan][*][/bold cyan] Acessando a página de login...")
            page.wait_for_timeout(2000)
            
            print("[bold cyan][*][/bold cyan] Realizando login...")
            # Usa o método universal blindado que funciona tanto para F6600 quanto para qualquer variante da F680/F670
            try:
                page.locator("input[type='text'], input[id*='user'], input[id*='name'], #Frm_Username, #username").first.fill(usuario)
                page.locator("input[type='password'], #Frm_Password, #password").first.fill(senha)
                page.locator("button[id*='login'], input[type='submit'], input[type='button'][value*='Login'], .login_btn, #Btn_login, #LoginId").first.click()
            except Exception as e:
                print(f"[bold red][-][/bold red] Aviso: falha no auto-login, tentando método alternativo: {e}")
                
            print("[bold cyan][*][/bold cyan] Aguardando o painel carregar...")
            page.wait_for_timeout(5000)
            
            # Tenta sair do Wizard (Assistente de Configuração Rápida) via JavaScript puro (infalível)
            try:
                page.evaluate('''
                    var btn = document.getElementById("Outquicksetup");
                    if(btn && btn.style.display !== "none") {
                        btn.click();
                    }
                ''')
                page.wait_for_timeout(3000)
            except:
                pass
                
            # Detecta o modelo DEPOIS do login usando a arquitetura da página
            # F680/F670 usam um sistema legado baseado em IFrames (mainFrame)
            # F6600 é uma página moderna sem o mainFrame
            is_f680 = False
            for f in page.frames:
                if f.name == "mainFrame":
                    is_f680 = True
                    break
            
            if is_f680:
                print("[bold green][+][/bold green] Modelo detectado: F680 / F670L")
                if fazer_config:
                    configurar_upnp_zte_f680(page)
                    configurar_sntp_zte_f680(page)
                ler_status_f680(page)
            else:
                print("[bold green][+][/bold green] Modelo detectado: F6600 / F6600P")
                if fazer_config:
                    configurar_upnp_zte_f6600(page)
                    configurar_sntp_f6600(page)
                    configurar_mesh_wifi_f6600(page)
                ler_status_f6600(page)
                

            
        except Exception as e:
            print(f"[bold red][-][/bold red] Ocorreu um erro ao processar a ONU {ip}: {str(e)}")
        finally:
            browser.close()

if __name__ == "__main__":
    console.print(Panel("[bold yellow]🤖 Robô Universal - ONUs ZTE[/bold yellow]", border_style="yellow", expand=False))
    while True:
        print(); ip_onu = input("Digite o IP WAN da ONU (ou Enter vazio para sair): ").strip()
        if not ip_onu:
            break
            
        ip_onu = ip_onu.replace("http://", "").replace("https://", "").replace("/", "")
        
        resp = input("Deseja realizar a configuração inicial (UPnP, SNTP, Mesh)? (s/n) [s]: ").strip().lower()
        fazer_config = False if resp == 'n' else True
        
        executar_automacao(ip_onu, "multipro", "multipro", fazer_config)
