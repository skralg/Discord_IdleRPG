import asyncio
import characters
import discord
import logging
import math
import os
import sqlite3
import time

from devmsg import devmsg
from dotenv import load_dotenv
from random import randint, seed

logging.basicConfig(level=logging.INFO)
load_dotenv()

seed()  # seed random generator


class IdleRPG(discord.Client):
    """
    The class from which all game things happen
    """
    rpbase = 600       # base time in seconds to level up, 600s = 10 minutes
    rpitemsbase = 200  # base time in seconds for items to decompose one level
    rpstep = 1.6       # Time to next level = rpbase * (rpstep ** level)
    rppenstep = 1.6    # penalty time = penalty * (rppenstep ** level)
    limitpen = 604800  # penalty max limited to 1 week of seconds
    self_clock = 3     # how often to run the event loop
    mapx = 1000        # custom size of map width
    mapy = 1000        # custom size of map height
    rpreport = 0       # timestamp for reporting top players
    oldrpreport = 0    # previous value for reporting top players
    lasttime = 1       # last time that rpcheck() was run. Used for time diff to shave next_ttl

    gamechan = None    # This text channel object will be filled in via on_ready()
    bg_task = None     # This gets set to loop the main loop

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.dbh = sqlite3.connect('irpg.db')
        self.characters = None

    async def setup_hook(self) -> None:
        devmsg('Setting up environment...')
        self.characters = characters.Characters(self.dbh)
        self.characters.load()
        # TODO: set up monsters
        # TODO: set up items
        # TODO: load map items
        devmsg('Environment set up.')

    async def on_ready(self):
        devmsg(f'Logged in as {self.user} {self.user!r}')
        # devmsg(f'guilds: {self.guilds}')
        for guild in self.guilds:
            for chan in guild.text_channels:
                if chan.name == 'idlerpg':
                    devmsg(f'  chan: {chan!r}')
                    self.gamechan = chan
                if chan.name == 'bot-commands':
                    devmsg(f'  chan: {chan!r}')
            for member in guild.members:
                if member.id == self.user.id:
                    continue
                # devmsg(f'member: {member!r}')
                # devmsg(f'member status: {member.status}')
                # devmsg(f'member activity: {member.activity!r}')
                # devmsg(f'member flags: {member.flags!r}')
                # find() will create the char if it doesn't exist
                tmp = self.characters.find(member)
                # devmsg(f'char: {tmp}')
                if member.status != 'offline':
                    self.characters.chars[tmp.id].online = 1  # set them online

        devmsg('Game starting!')
        self.lasttime = int(time.time())
        self.bg_task = self.loop.create_task(self.mainloop())

    async def on_message(self, message):
        if message.author.id == self.user.id:
            return
        if message.content.startswith('!test'):
            await message.channel.send('got your test')
            # await message.reply('Yeah, got your test', mention_author=True)
        else:
            if message.channel.name == 'idlerpg':
                # TODO: Penalize player
                character_id = message.author.id
                name = message.author.global_name
                if name is None:
                    name = message.author.name
                devmsg(message)
                devmsg(message.content)
                pen = self.penalize(character_id, 'message', len(message.content))
                dur = self.duration(pen)
                await self.gamechan.send(f"Penalty of {dur} added to {name}'s timer for a message.")

            if message.channel.name == 'bot-commands':
                # TODO: implement bot commands, like !whoami
                # TODO: refactor top5, as it's duplicated in rpcheck
                if message.content == '!top5':
                    chars = self.characters.topx(5)
                    await self.gamechan.send('Idle RPG Top 5 Players:')
                    x = 1
                    for char in chars:
                        dur = self.duration(char.next_ttl)
                        # devmsg(f"{char.username}, the {char.charclass}, is #{x}! Next level in {dur}.")
                        await self.gamechan.send(f"{char.username}, the {char.charclass}, is #{x}! Next level in {dur}.")
                        x += 1
                    return

                devmsg('unimplemented')
                await message.channel.send('bot commands unimplemented as yet')

    async def on_message_edit(self, before, after):
        # devmsg(f'a message was edited from {before} to {after}')
        if before.channel.name == 'idlerpg':
            return
        old_length = len(before.content)
        new_length = len(after.content)
        difference = abs(old_length - new_length)
        if difference == 0:
            difference = 1
        character_id = after.author.id
        name = after.author.global_name
        if name is None:
            name = after.author.name
        pen = self.penalize(character_id, 'message', difference)
        dur = self.duration(pen)
        await self.gamechan.send(f"Penalty of {dur} added to {name}'s timer for editing a message.")

    # This could be helpful for message deletes eventually
    async def SKIPon_audit_log_entry_create(self, entry):
        devmsg(f"{entry!r}")
        self.dump_audit_log_entry(entry)

    # TODO: Maybe we'll work on this in the future.
    # For now, we'll just skip message deletions
    async def SKIPon_message_delete(self, message):
        # Skip if this isn't on the game channel
        if message.channel != self.gamechan:
            return
        devmsg(f'a message was deleted: {message}')
        # Skip if it was someone deleting one of our messages
        if message.author == self.user:
            # devmsg(f"ended: author of deleted message ({message.author}) is us")
            return
        # Skip if the author isn't a player somehow
        if self.characters.find(message.author) is None:
            # devmsg(f'ended: author ({message.author}) is not playing')
            return
        # At this point, we need to check to see if a mod did the delete
        # If not, then we penalize the player for the content length again
        guild = self.get_guild(message.author.guild.id)
        async for entry in guild.audit_logs(action=discord.AuditLogAction.message_delete, limit=10):
            self.dump_audit_log_entry(entry)
        length = len(message.content)
        # devmsg(f"message content: {message.content} with length {length}")
        character_id = message.author.id
        name = message.author.global_name
        if name is None:
            name = message.author.name
        pen = self.penalize(character_id, 'message', length)
        dur = self.duration(pen)
        await self.gamechan.send(f"Penalty of {dur} added to {name}'s timer for deleting a message.")

    async def on_reaction_add(self, reaction, user):
        devmsg(f'{user} added a reaction to {reaction.message}')
        # TODO: Penalize somehow

    async def on_reaction_remove(self, reaction, user):
        devmsg(f'{user} removed a reaction to {reaction.message}')
        # TODO: Penalize somehow

    # TODO: Add thread interaction penalties
    async def on_member_join(self, member):
        guild = member.guild
        if guild.system_channel is not None:
            to_send = f'Welcome {member.mention} to {guild.name}!'
            await guild.system_channel.send(to_send)
        # TODO: check for player in db, create if not present
        # TODO: log player in

    async def on_member_remove(self, member):
        guild = member.guild
        devmsg(f'member {member.mention} left {guild.name}')
        # TODO: log out player, keep in db, they could play elsewhere

    async def on_member_update(self, before, after):
        devmsg(f'member {before.nickname} updated profile')
        # TODO: Penalize

    async def on_user_update(self, before, after):
        devmsg(f'user {before.nickname} updated profile')
        # TODO: Penalize

    async def on_member_ban(self, guild, user):
        devmsg(f'user {user} was banned from {guild}')
        # TODO: Penalize

    async def on_presence_update(self, member_before, member_after):
        name = member_before.global_name
        if name is None:
            name = member_before.name
        character = self.characters.find(member_before)
        devmsg(f'character: {character!r}')
        devmsg(f'Member "{name}" updated presence')
        if member_before.status != member_after.status:
            bef = member_before.status
            aft = member_after.status
            devmsg(f'before status: {bef!r}')
            devmsg(f'after  status: {aft!r}')
            pen = self.penalize(character.id, 'status')
            dur = self.duration(pen)
            await self.gamechan.send(f"Penalty of {dur} added to {name}'s timer for status change of '{bef}' to '{aft}'.")
        if member_before.activity != member_after.activity:
            bef = member_before.activity
            aft = member_after.activity
            devmsg(f'before activity: {bef!r}')
            devmsg(f'after  activity: {aft!r}')
            pen = self.penalize(character.id, 'activity')
            dur = self.duration(pen)
            devmsg(f"pen({pen}) dur({dur})")
            await self.gamechan.send(f"Penalty of {dur} added to {name}'s timer for activity change of '{bef}' to '{aft}'.")

        if character.online == 0:
            return
        # TODO: Penalize

    async def on_connect(self):
        devmsg('connected')

    async def on_disconnect(self):
        devmsg('disconnected')

    async def on_shard_connect(self):
        devmsg('shard connected')

    async def on_shard_disconnect(self):
        devmsg('shard disconnected')

    async def on_resumed(self):
        devmsg('resumed')

    async def mainloop(self):
        """
        This is the function that keeps us moving
        :return: None
        """
        devmsg('start')
        await self.rpcheck()

        # Wait self_clock seconds and start mainloop() over
        devmsg('sleeping')
        await asyncio.sleep(self.self_clock)
        devmsg('creating task')
        self.bg_task = self.loop.create_task(self.mainloop())
        devmsg('ended')

    async def rpcheck(self):
        """
        The meat and bones of the whole operation. Well, excluding the event penalties.
        :return: None
        """
        devmsg('start')
        # Get a list of online users
        online = self.characters.online()
        online_good = self.characters.online(alignment='g')
        online_evil = self.characters.online(alignment='e')
        devmsg('got char lists')

        online_count = len(online)
        # If nobody is online, we have nothing to do
        if online_count == 0:
            devmsg('ended: nobody online')
            return
        devmsg('checking randoms for general events')
        if randint(0, int(24 * 86400 / self.self_clock)) < online_count: await self.monster_hunt()
        if randint(0, int(20 * 86400 / self.self_clock)) < online_count: await self.hand_of_god()
        if randint(0, int(9  * 86400 / self.self_clock)) < online_count: await self.group_battle()
        if randint(0, int(9  * 86400 / self.self_clock)) < online_count: await self.team_battle()
        if randint(0, int(8  * 86400 / self.self_clock)) < online_count: await self.calamity()
        if randint(0, int(8  * 86400 / self.self_clock)) < online_count: await self.godsend()
        if randint(0, int(8  * 14400 / self.self_clock)) < online_count: await self.celebrity_fight()  # beast_opp in Perl
        if randint(0, int(8  * 19400 / self.self_clock)) < online_count: await self.random_gold()
        if randint(0, int(8  * 43200 / self.self_clock)) < online_count: await self.monster_attack()

        # Do the following if at least 15% of the characters are online
        devmsg('checking randoms for good/evil events')
        if online_count / len(self.characters.chars) > .15:
            if randint(0, int(8  * 86400 / self.self_clock)) < len(online_good): await self.random_steal()
            if randint(0, int(12 * 86400 / self.self_clock)) < len(online_evil): await self.evilness()
            if randint(0, int(12 * 86400 / self.self_clock)) < len(online_good): await self.goodness()
            if randint(0, int(20 * 86400 / self.self_clock)) < len(online_good): await self.godsend()

        # Always do the following
        await self.moveplayers()
        await self.process_items()

        # TODO: Quests
        devmsg('todo: quests')

        # Hourly Tasks  (TODO: fact check 'Hourly')
        if self.rpreport and (self.rpreport % 3600 < self.oldrpreport % 3600):
            devmsg('doing hourly tasks')
            # Reseed random
            seed()

            chars = self.characters.topx(5)
            await self.gamechan.send('Idle RPG Top 5 Players:')
            x = 1
            for char in chars:
                # await self.gamechan.send(line)
                dur = self.duration(char.next_ttl)
                devmsg(f"{char.username}, the {char.charclass}, is #{x}! Next level in {dur}.")
                await self.gamechan.send(f"{char.username}, the {char.charclass}, is #{x}! Next level in {dur}.")
                x += 1

            await self.announce_next_tournament()

            # TODO: random_challenge, hourly, 15% of all players must be level 25+ irpg.pl:2643

        # Decrement next_ttl, level up, etc
        devmsg('doing instant tasks')
        curtime = int(time.time())
        for char_id in self.characters.online():
            char = self.characters.chars[char_id]
            devmsg(f'processing char {char}')
            delta = curtime - self.lasttime
            char.next_ttl -= delta
            char.idled += delta
            devmsg(f"{char.username} ttl is {char.next_ttl}")
            if char.next_ttl < 1:
                devmsg(f"{char.username} leveled...")
                nextlevel = char.level + 1
                base_ttl = self.base_ttl(nextlevel)
                devmsg(f"got new ttl of {base_ttl}")
                char.level += 1
                char.next_ttl = base_ttl
                nextlevel += 1
                char.popcorn = 0
                char.regentime = 0
                char.challengetime = 0
                char.slaytime = 0
                if char.level < 200:
                    char.ffight = 0
                char.bets = 0
                char.pot = 0
                self.characters.chars[char_id] = char
                self.characters.update(char_id)
                devmsg('updated char in db')
                heshe = char.heshe(uppercase=1)
                devmsg(f"heshe: {heshe}")
                dur = self.duration(base_ttl)
                await self.gamechan.send(f"{char.username}, {char.charclass}, has attained level {char.level}! {heshe} reaches level {nextlevel} in {dur}.")
                self.find_item(char_id)
                self.find_gold(char_id)
                self.random_challenge(char_id)
                self.monster_attack_player(char_id)

        self.characters.updatedb()
        self.oldrpreport = self.rpreport
        self.rpreport += curtime - self.lasttime
        self.lasttime = curtime

        # Tournaments
        # TODO: irpg.pl:2720
        devmsg('ended')

    def monster_attack_player(self, char_id):
        devmsg('start')
        # await self.gamechan.send(f"TODO: Monster Attack Player!")
        devmsg('ended')

    def random_challenge(self, char_id):
        devmsg('start')
        # await self.gamechan.send(f"TODO: Random Challenge!")
        devmsg('ended')

    def find_gold(self, char_id):
        devmsg('start')
        # await self.gamechan.send(f"TODO: Find Gold!")
        devmsg('ended')

    def find_item(self, char_id):
        devmsg('start')
        # await self.gamechan.send(f"TODO: Find Item!")
        devmsg('ended')

    def base_ttl(self, level) -> int:
        """
        Calculates the base ttl for a character
        :param level: character level
        :return: integer seconds on Time-To-Level
        """
        if level <= 60:
            return int(self.rpbase * math.pow(self.rpstep, level))
        return int(self.rpbase * (math.pow(self.rpstep, 60)) + (86400 * (level - 60)))

    async def announce_next_tournament(self):
        await self.gamechan.send("TODO: Announce Next Tournament!")

    async def process_items(self):
        # devmsg('start')
        # await self.gamechan.send(f"TODO: Random Steal!")
        devmsg('ended')

    async def moveplayers(self):
        # devmsg('start')
        # await self.gamechan.send(f"TODO: Move Players!")
        devmsg('ended')

    async def goodness(self):
        devmsg('start')
        await self.gamechan.send(f"TODO: Random Goodness!")
        devmsg('ended')

    async def evilness(self):
        devmsg('start')
        await self.gamechan.send(f"TODO: Random Evilness!")
        devmsg('ended')

    async def random_steal(self):
        devmsg('start')
        await self.gamechan.send(f"TODO: Random Steal!")
        devmsg('ended')

    async def monster_attack(self):
        devmsg('start')
        await self.gamechan.send(f"TODO: Monster Attack!")
        devmsg('ended')

    async def random_gold(self):
        devmsg('start')
        await self.gamechan.send(f"TODO: Random Gold!")
        devmsg('ended')

    async def celebrity_fight(self):
        devmsg('start')
        await self.gamechan.send(f"TODO: Celebrity Fight!")
        devmsg('ended')

    async def godsend(self):
        devmsg('start')
        await self.gamechan.send(f"TODO: Godsend!")
        devmsg('ended')

    async def calamity(self):
        devmsg('start')
        await self.gamechan.send(f"TODO: Calamity!")
        devmsg('ended')

    async def team_battle(self):
        devmsg('start')
        await self.gamechan.send(f"TODO: Team Battle!")
        devmsg('ended')

    async def group_battle(self):
        devmsg('start')
        await self.gamechan.send(f"TODO: Group Battle!")
        devmsg('ended')

    async def hand_of_god(self):
        devmsg('start')
        await self.gamechan.send(f"TODO: Hand of God!")
        devmsg('ended')

    async def monster_hunt(self):
        devmsg('start')
        await self.gamechan.send(f"TODO: Monster Hunt!")
        devmsg('ended')

    def penalize(self, character_id, pen_type, *args) -> int:
        # get local copy of character
        character = self.characters.chars[character_id]
        penalty_ttl = self.penttl(character.level)
        if pen_type == "status" or pen_type == "activity":
            devmsg(f"{character} gets '{pen_type}' penalty")
            pen = int(30 * penalty_ttl / self.rpbase)
            if pen > self.limitpen:
                pen = self.limitpen
            devmsg(f'pen: {pen}')
            # TODO: pen_nick is legacy from IRC. Make new counters for pen_status and pen_activity
            character.pen_nick += pen
            character.next_ttl += pen
            # copy local character back to the global character list
            self.characters.chars[character_id] = character
            # tell it to update itself in the db
            self.characters.update(character_id)
            return pen
        elif pen_type == "message":
            length = args[0]
            penalty_ttl = self.penttl(character.level, ignore_level=True)
            pen = int(length * penalty_ttl)
            if pen > self.limitpen:
                pen = self.limitpen
            character.pen_msg += pen
            character.next_ttl += pen
            # copy local character back to the global character list
            self.characters.chars[character_id] = character
            # tell it to update itself in the db
            self.characters.update(character_id)
            return pen
        else:
            devmsg(f"{character} gets an unhandled '{pen_type}' penalty")
            return 600

    def penttl(self, level, ignore_level=False):
        """
        Calculate the magnitude of a penalty in ttl
        :param level: character's level
        :param ignore_level: choose to ignore level 60 adjustment
        :return: amount of seconds to penalize
        """
        if level <= 60 or ignore_level == True:
            return self.rpbase * math.pow(self.rppenstep, level)
        else:
            return (self.rpbase * math.pow(self.rppenstep, 60)) + (86400 * (level - 60))

    @staticmethod
    def duration(seconds):
        """
        :param seconds: a count of seconds
        :return: human-readable duration of said seconds
        """
        if seconds is None or seconds <= 0:
            return 'a moment'
        return '%d day%s, %02d:%02d:%02d' % (
            seconds / 86400,
            '' if math.trunc(seconds / 86400) == 1 else 's',
            (seconds % 86400) / 3600,
            (seconds % 3600) / 60,
            (seconds % 60)
        )

    @staticmethod
    def dump_audit_log_entry(entry):
        devmsg(f"action: {entry.action}")
        devmsg(f"user who initiated: {entry.user}")
        devmsg(f"user_id: {entry.user_id}")
        devmsg(f"id: {entry.id}")
        devmsg(f"guild: {entry.guild}")
        devmsg(f"target: {entry.target}")
        devmsg(f"reason: {entry.reason}")
        devmsg(f"extra: {entry.extra!r}")
        devmsg(f"created at: {entry.created_at}")
        devmsg(f"category: {entry.category}")
        devmsg(f"changes: {entry.changes!r}")
        devmsg(f"before: {entry.before!r}")
        devmsg(f"after: {entry.after!r}")


intents = discord.Intents.all()
game = IdleRPG(intents=intents)
game.run(os.getenv('DISCORD_TOKEN'))

