import discord
from discord.ext import commands
import random
import requests
import base64
from io import BytesIO
import asyncio
import time
import uuid
import json
from dotenv import load_dotenv
import os

# 🔑 Carregar variáveis do .env
load_dotenv()

TOKEN_DISCORD = os.getenv("DISCORD_TOKEN")
MERCADO_PAGO_TOKEN = os.getenv("MERCADO_PAGO_TOKEN")
SEU_EMAIL = os.getenv("EMAIL")

intents = discord.Intents.default()
intents.messages = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# 🎰 Lista de prêmios
premios = [
    {"nome": "💎 Bicicleteira 14M/s", "chance": 1},
    {"nome": "✨ Secret 1-5M/s", "chance": 9},
    {"nome": "🔥 Brainrot 1-2M/s", "chance": 40},
    {"nome": "⚡ Brainrot 500K/s", "chance": 30},
    {"nome": "🥹 brainrot 10k - 400k", "chance": 20},
]

# Dicionário para rastrear o pity counter por usuário
pity_counters = {}

def girar_roleta(user_id):
    global pity_counters
    
    # Inicializar o contador de pity se não existir
    if user_id not in pity_counters:
        pity_counters[user_id] = 0
    
    # Verificar se o usuário atingiu o pity (20 giros sem ganhar o prêmio de 1%)
    if pity_counters[user_id] >= 20:
        pity_counters[user_id] = 0  # Resetar o contador
        return "💎 Bicicleteira 14M/s"
    
    # Girar a roleta normalmente
    roll = random.uniform(0, 100)
    acumulado = 0
    for premio in premios:
        acumulado += premio["chance"]
        if roll <= acumulado:
            # Se não ganhou o prêmio de 1%, incrementar o contador de pity
            if premio["nome"] != "💎 Bicicleteira 14M/s":
                pity_counters[user_id] += 1
            else:
                pity_counters[user_id] = 0  # Resetar se ganhou o prêmio raro
            return premio["nome"]

# 🎯 Criar pagamento Pix no Mercado Pago (com SEU email)
def criar_pagamento_pix(valor: float, user_id: str, giros: int):
    url = "https://api.mercadopago.com/v1/payments"
    
    # Gerar um ID único para a idempotência
    idempotency_key = str(uuid.uuid4())
    
    headers = {
        "Authorization": f"Bearer {MERCADO_PAGO_TOKEN}",
        "Content-Type": "application/json",
        "X-Idempotency-Key": idempotency_key
    }
    
    # Gera um ID único para a transação
    external_reference = f"roleta_{user_id}_{int(time.time())}"
    
    data = {
        "transaction_amount": valor,
        "description": f"Giro da Roleta 🎰 ({giros} giros)",
        "payment_method_id": "pix",
        "external_reference": external_reference,
        "payer": {
            "email": SEU_EMAIL,
            "first_name": "Discord",
            "last_name": f"User{user_id}",
        }
    }
    
    try:
        r = requests.post(url, headers=headers, json=data)
        response = r.json()
        
        if r.status_code == 201:
            return response
        else:
            print(f"Erro ao criar pagamento: {response}")
            return None
    except Exception as e:
        print(f"Exceção ao criar pagamento: {e}")
        return None

# 🎯 Consultar status do pagamento
def consultar_pagamento(payment_id):
    url = f"https://api.mercadopago.com/v1/payments/{payment_id}"
    headers = {"Authorization": f"Bearer {MERCADO_PAGO_TOKEN}"}
    
    try:
        r = requests.get(url, headers=headers)
        return r.json()
    except Exception as e:
        print(f"Erro ao consultar pagamento: {e}")
        return None

# Classe para os botões de seleção de giros
class SelecionarGirosView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=120)
    
    @discord.ui.select(
        placeholder="🎰 Selecione quantos giros",
        options=[
            discord.SelectOption(label="1 Giro - R$ 1,00", value="1", emoji="🎲"),
            discord.SelectOption(label="3 Giros - R$ 3,00", value="3", emoji="🎰"),
            discord.SelectOption(label="5 Giros - R$ 5,00", value="5", emoji="💰"),
            discord.SelectOption(label="10 Giros - R$ 10,00", value="10", emoji="💎"),
            discord.SelectOption(label="20 Giros - R$ 20,00", value="20", emoji="🔥"),
        ]
    )
    async def select_giros(self, interaction: discord.Interaction, select: discord.ui.Select):
        try:
            await interaction.response.defer(ephemeral=True, thinking=True)
            
            giros = int(select.values[0])
            valor_total = giros * 1.0
            
            # Gerar Pix
            pagamento = criar_pagamento_pix(valor_total, str(interaction.user.id), giros)
            
            if not pagamento or "point_of_interaction" not in pagamento:
                error_msg = "❌ Erro ao gerar pagamento Pix. Tente novamente mais tarde."
                if pagamento and 'message' in pagamento:
                    error_msg += f"\nErro: {pagamento['message']}"
                await interaction.followup.send(error_msg, ephemeral=True)
                return

            payment_id = pagamento["id"]
            qr_code = pagamento["point_of_interaction"]["transaction_data"]["qr_code"]
            qr_img_b64 = pagamento["point_of_interaction"]["transaction_data"]["qr_code_base64"]

            # Converter imagem base64 em arquivo
            qr_img_bytes = base64.b64decode(qr_img_b64)
            img_file = discord.File(BytesIO(qr_img_bytes), filename="qrcode.png")
            
            # Informações adicionais do Pix
            pix_copy_paste = pagamento["point_of_interaction"]["transaction_data"].get("qr_code", "")
            
            if len(pix_copy_paste) > 100:
                partes = [pix_copy_paste[i:i+80] for i in range(0, len(pix_copy_paste), 80)]
                texto_copia_cola = "\n".join(partes)
            else:
                texto_copia_cola = pix_copy_paste

            embed = discord.Embed(
                title="💰 Pagamento via PIX",
                description=f"**Quantidade de giros:** {giros}\n**Valor total:** R$ {valor_total:.2f}\n\nEscaneie o QR Code abaixo ou use o código Pix Copia e Cola:",
                color=discord.Color.green()
            )
            
            if texto_copia_cola:
                embed.add_field(
                    name="📋 Código PIX (Copia e Cola)", 
                    value=f"```\n{texto_copia_cola}\n```", 
                    inline=False
                )
            
            embed.add_field(
                name="📱 QR Code",
                value="Use o QR Code abaixo para pagar com seu app bancário:",
                inline=False
            )
            
            embed.set_footer(text="⚠️ Você tem 10 minutos para realizar o pagamento!")

            await interaction.followup.send(embed=embed, ephemeral=True)
            
            embed_imagem = discord.Embed(
                title="",
                description="",
                color=discord.Color.green()
            )
            embed_imagem.set_image(url="attachment://qrcode.png")
            
            await interaction.followup.send(
                embed=embed_imagem,
                file=img_file,
                ephemeral=True
            )

            # 🔄 Checar automaticamente até aprovar
            await asyncio.sleep(10)
            
            for i in range(30):
                pagamento_status = consultar_pagamento(payment_id)
                
                if pagamento_status and pagamento_status.get("status") == "approved":
                    resultados = []
                    for _ in range(giros):
                        resultado = girar_roleta(str(interaction.user.id))
                        resultados.append(resultado)
                    
                    # Formatar resultados
                    resultados_formatados = "\n".join([f"🎲 Giro {i+1}: {resultado}" for i, resultado in enumerate(resultados)])
                    
                    # Mostrar contador de pity atual
                    pity_atual = pity_counters.get(str(interaction.user.id), 0)
                    info_pity = f"\n\n📊 Seu contador de pity: {pity_atual}/20"
                    
                    # 🔥 MENSAGEM PÚBLICA - Mostrar para todos o resultado
                    public_embed = discord.Embed(
                        title="🎉 TEMOS UM GANHADOR!",
                        description=f"**{interaction.user.mention} girou {giros} vezes na roleta e ganhou:**\n\n{resultados_formatados}",
                        color=discord.Color.gold()
                    )
                    if interaction.user.avatar:
                        public_embed.set_thumbnail(url=interaction.user.avatar.url)
                    public_embed.set_footer(text=f"Total de giros: {giros} | Valor: R$ {valor_total:.2f}")
                    
                    if interaction.channel:
                        await interaction.channel.send(embed=public_embed)
                    
                    # Mensagem privada de confirmação
                    result_embed = discord.Embed(
                        title="✅ Pagamento confirmado!",
                        description=f"Seus prêmios ({giros} giros):\n\n{resultados_formatados}{info_pity}",
                        color=discord.Color.green()
                    )
                    await interaction.followup.send(embed=result_embed, ephemeral=True)
                    return
                    
                elif pagamento_status and pagamento_status.get("status") in ["cancelled", "rejected", "refunded"]:
                    await interaction.followup.send("❌ Pagamento cancelado ou rejeitado.", ephemeral=True)
                    return
                    
                await asyncio.sleep(10)

            await interaction.followup.send("⚠️ Pagamento não identificado dentro do tempo limite. Se você pagou, entre em contato com o suporte.", ephemeral=True)
        
        except discord.errors.NotFound:
            print("Interação expirada - usuário demorou muito para clicar")
        except Exception as e:
            print(f"Erro inesperado: {e}")
            try:
                await interaction.followup.send("❌ Ocorreu um erro inesperado. Tente novamente.", ephemeral=True)
            except:
                pass

# Classe para o botão de suporte
class SuporteView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="Suporte 📩", style=discord.ButtonStyle.secondary, custom_id="suporte")
    async def suporte_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            await interaction.response.send_message("📩 Entre em contato com o suporte para tirar dúvidas!", ephemeral=True)
        except discord.errors.NotFound:
            pass

# Evento quando bot está online
@bot.event
async def on_ready():
    print(f"✅ Bot conectado como {bot.user}")
    # Adiciona a view persistente
    bot.add_view(SuporteView())

# Comando tradicional com prefixo "!"
@bot.command()
async def roleta(ctx):
    embed = discord.Embed(
        title="🎰 Roleta da Sorte 🎲",
        description="💵 Apenas R$ 1,00 por giro!\n✨ Concorrendo a **Bicicleteira** e vários outros prêmios!\n\n🎯 **Sistema de Pity**: Garantia de ganhar a Bicicleteira a cada 20 giros!",
        color=discord.Color.red()
    )
    embed.add_field(name="🏆 Melhor prêmio", value="💎 Bicicleteira 14M/s", inline=False)
    embed.add_field(name="💰 Preços", value="1 Giro = R$ 1,00\n3 Giros = R$ 3,00\n5 Giros = R$ 5,00\n10 Giros = R$ 10,00\n20 Giros = R$ 20,00", inline=False)
    embed.add_field(name="🎯 Sistema de Pity", value="Seu contador de pity aumenta a cada giro sem ganhar a Bicicleteira. Ao atingir 20, você garante o prêmio!", inline=False)

    lista_premios = "\n".join([f"{p['nome']} ({p['chance']}% chance)" for p in premios])
    embed.add_field(name="🎁 Prêmios disponíveis", value=lista_premios, inline=False)

    embed.set_image(url="https://i.ytimg.com/vi/Nk5Kxp0xWRk/maxresdefault.jpg")
    embed.set_footer(text="Selecione quantos giros deseja abaixo!")

    await ctx.send(embed=embed, view=SelecionarGirosView())
    await ctx.send("📩 Precisa de ajuda?", view=SuporteView())

# Comando para verificar pity atual
@bot.command()
async def pity(ctx):
    user_id = str(ctx.author.id)
    pity_atual = pity_counters.get(user_id, 0)
    
    embed = discord.Embed(
        title="📊 Seu Contador de Pity",
        description=f"Seu contador atual: **{pity_atual}/20**",
        color=discord.Color.blue()
    )
    embed.add_field(
        name="🎯 Como funciona?",
        value="A cada giro sem ganhar a **💎 Bicicleteira 14M/s**, seu contador aumenta. Ao atingir 20, você garante este prêmio no próximo giro!",
        inline=False
    )
    embed.add_field(
        name="💡 Dica",
        value="Quanto mais giros você fizer, mais chances tem de ganhar prêmios raros!",
        inline=False
    )
    
    await ctx.send(embed=embed)

# Comando de ajuda tradicional
@bot.command()
async def ajuda(ctx):
    embed = discord.Embed(
        title="❓ Ajuda - Roleta da Sorte",
        description="Como usar o bot da roleta da sorte:",
        color=discord.Color.blue()
    )
    embed.add_field(
        name="🎰 Girar a roleta",
        value="Use `!roleta` para abrir a roleta e selecione quantos giros deseja. Cada giro custa R$ 1,00 via PIX.",
        inline=False
    )
    embed.add_field(
        name="💳 Como pagar",
        value="1. Selecione quantos giros quer\n2. Copie o código PIX ou escaneie o QR Code\n3. Pague o valor total no seu app bancário\n4. Aguarde a confirmação automática",
        inline=False
    )
    embed.add_field(
        name="🎯 Sistema de Pity",
        value="Use `!pity` para ver seu contador atual. A cada 20 giros sem ganhar a Bicicleteira, você garante este prêmio!",
        inline=False
    )
    embed.add_field(
        name="🎉 Resultados",
        value="• Os resultados são anunciados publicamente para todos verem!\n• Você recebe todos os prêmios dos giros\n• Quanto mais giros, mais chances de ganhar!",
        inline=False
    )
    embed.add_field(
        name="💰 Preços",
        value="1 Giro = R$ 1,00\n3 Giros = R$ 3,00\n5 Giros = R$ 5,00\n10 Giros = R$ 10,00\n20 Giros = R$ 20,00",
        inline=False
    )
    embed.add_field(
        name="⚠️ Problemas",
        value="Se encontrar qualquer problema, clique no botão de suporte.",
        inline=False
    )
    
    await ctx.send(embed=embed)

# Comando para ver últimos ganhadores
@bot.command()
async def ganhadores(ctx):
    embed = discord.Embed(
        title="🏆 Últimos Ganhadores",
        description="Os resultados mais recentes da roleta da sorte:",
        color=discord.Color.gold()
    )
    embed.add_field(
        name="🔔 Atenção",
        value="Use `!roleta` para participar e talvez você seja o próximo ganhador anunciado aqui!",
        inline=False
    )
    embed.set_footer(text="A roleta da sorte está sempre girando! 🎰")
    
    await ctx.send(embed=embed)

bot.run(TOKEN_DISCORD)