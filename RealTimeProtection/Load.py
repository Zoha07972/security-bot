from discord.ext import commands
from .RaidDetection import RaidDetectionCog
from .AntiSpam import AntiSpamCog
async def setup(bot: commands.Bot):
    await bot.add_cog(RaidDetectionCog(bot))
    await bot.add_cog(AntiSpamCog(bot))