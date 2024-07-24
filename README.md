# Discord IdleRPG
A reimplementation of the classic IRC IdleRPG for Discord servers

For a current working game, please visit #idlerpg at https://discord.gg/kzvpYkyN7g

A .env file in the base directory is required for the discord bot to connect.
Its contents should be something like the following:
  DISCORD_TOKEN=<discord token you created>
  DISCORD_GUILD=<Name of your discord server>

A python virtual environment is suggested.
The following python packages are required:
  quart
  discord
  python-dotenv
