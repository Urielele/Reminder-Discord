import discord
from discord.ext import commands
import pandas as pd

df = None

def read_data():
    global df
    df = pd.read_excel('.\cogs\database\Schedule.xlsx')
    df["dl_tugas"] = df["dltgl_tugas"].astype(str) + " " + df["dljm_tugas"].astype(str)
    df["fdltgl_tugas"] = df['dltgl_tugas'].dt.strftime('%B %d, %Y')
    
    
class Reminder(commands.Cog):    

    def __init__(self, bot):
        self.bot = bot
    
    @commands.Cog.listener()
    async def on_ready(self):
        read_data()
        print("Reminder.py is ready")

    @commands.command()
    async def tugas(self, ctx, id: int = None):

        if id is None:
            await ctx.send("❓ Gunakan **!tugas <ID>**")
            return

        try:
            result = df[df['id_tugas'] == id].iloc[0]
        except IndexError:
            await ctx.send("❗ Tugas dengan ID tersebut tidak ditemukan.")
            return

        embed = discord.Embed(
            title=result['matkul_tugas'],
            description=result['desk_tugas'],
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="📆 Tanggal",
            value=result['fdltgl_tugas'],
            inline=True
        )

        embed.add_field(
            name="⏰ Jam",
            value=result['dljm_tugas'],
            inline=True
        )
        
        embed.set_footer(text=f"ID Tugas: {id}")

        await ctx.send(embed=embed)


    @commands.command()
    async def daftar_tugas(self, ctx):
        show = df[['matkul_tugas', "dl_tugas", "id_tugas"]]

        embed = discord.Embed(
            title="📚 Daftar Tugas",
            color=discord.Color.blue()
        )

        for _, row in show.iterrows():
            embed.add_field(
                name=f"{row['matkul_tugas']} (ID = {row['id_tugas']})",
                value=f"🕒 {row['dl_tugas']}",
                inline=False
            )

        await ctx.send(embed=embed)
    
    


async def setup(bot):
    await bot.add_cog(Reminder(bot))