from discord.ext import commands
from Config.Config import ConfigCog
from Config.Logs import LogsCog

async def setup(bot: commands.Bot):
    await bot.add_cog(ConfigCog(bot))
    await bot.add_cog(LogsCog(bot))