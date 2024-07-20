"""
This is the engine that connects to the MQ. All game logic is done here.
Endpoints will connect directly to the MQ as well, allowing them to restart
without affecting the game engine itself.
"""
import asyncio
from threading import Thread
import characters
import discord
import logging
import math
import os
import sqlite3
import time

from dotenv import load_dotenv
from quart import Quart, request, render_template
from random import choice, randint, seed, uniform

from devmsg import devmsg

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
    mapx = 851         # custom size of map width
    mapy = 700         # custom size of map height
    rpreport = 0       # timestamp for reporting top players
    oldrpreport = 0    # previous value for reporting top players
    lasttime = 1       # last time that rpcheck() was run. Used for time diff to shave next_ttl

    gamechan = None    # This text channel object will be filled in via on_ready()
    bg_task = None     # This gets set to loop the main loop

    # Server roles. Default to none, will load when the bot is connected
    role_online = None
    role_idle = None
    role_dnd = None

    # Track our loop so we don't get multiples started
    loop_started = False

    # Items on the map. Dict of dicts of a list of dicts. It really does make sense.
    map_items = {}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.dbh = sqlite3.connect('irpg.db')
        self.characters = characters.Characters(self.dbh)
        self.characters.load()

    async def setup_hook(self) -> None:
        devmsg('Setting up environment...')
        # self.characters = characters.Characters(self.dbh)
        # self.characters.load()
        # TODO: set up monsters
        # TODO: set up items
        # TODO: load map items
        devmsg('Environment set up.')

    async def on_ready(self):
        devmsg(f'Logged in as {self.user} {self.user!r}')
        # devmsg(f'guilds: {self.guilds}')
        for guild in self.guilds:
            for role in guild.roles:
                # No need for role_offline, it's handled
                devmsg(f"Role: {role!r}")
                if role.name == 'Idle':
                    self.role_idle = role
                elif role.name == 'Online':
                    self.role_online = role
                elif role.name == 'DND':
                    self.role_dnd = role
            if self.role_idle is None:
                self.role_idle = await guild.create_role(
                    name='Idle',
                    color=discord.Colour.blue(),
                    hoist=True,
                    reason='Required for IdleRPG Game',
                )
            if self.role_online is None:
                self.role_online = await guild.create_role(
                    name='Online',
                    color=discord.Colour.lighter_grey(),
                    hoist=True,
                    reason='Required for IdleRPG Game',
                )
            if self.role_dnd is None:
                self.role_dnd = await guild.create_role(
                    name='DND',
                    color=discord.Colour.lighter_grey(),
                    hoist=True,
                    reason='Required for IdleRPG Game',
                )
            await guild.edit_role_positions(
                reason='IdleRPG game logic',
                positions={
                    self.role_dnd: 0,
                    self.role_online: 1,
                    self.role_idle: 2,
                }
            )

            for chan in guild.text_channels:
                if chan.name == 'idlerpg':
                    # devmsg(f'  chan: {chan!r}')
                    self.gamechan = chan
                if chan.name == 'bot-commands':
                    # devmsg(f'  chan: {chan!r}')
                    pass
            for member in guild.members:
                if member.id == self.user.id:
                    continue
                # devmsg(f'member: {member!r}')
                # devmsg(f'member status: {member.status}')
                # devmsg(f'member activity: {member.activity!r}')
                # devmsg(f'member flags: {member.flags!r}')
                # find() will create the char if it doesn't exist
                tmp = self.characters.find(member)
                # devmsg(f'char: {tmp!r}')
                # devmsg(f"member status: '{member.status!r}' and online: {tmp.online}")
                await self.set_player_roles(member)
                if member.raw_status == 'offline':
                    if tmp.online == 1:
                        tmp.online = 0  # set them offline
                        self.characters.update(tmp)
                else:
                    if tmp.online == 0:
                        tmp.online = 1  # set them online
                        self.characters.update(tmp)

        devmsg('Game starting!')
        self.lasttime = int(time.time())
        if not self.loop_started:
            self.bg_task = self.loop.create_task(self.mainloop())

    async def on_message(self, message):
        if message.author.id == self.user.id:
            return
        else:
            char = self.characters.find(message.author)
            # devmsg(f"char({char.username}) chan({message.channel.name}) message({message.content})")
            if message.channel.name == 'idlerpg':
                devmsg(message)
                devmsg(message.content)
                pen = self.penalize(char, 'message', len(message.content))
                dur = self.duration(pen)
                await self.gamechan.send(f"Penalty of {dur} added to {char.username}'s timer for a message.")
                return

            elif message.channel.name == 'bot-commands':
                # implement bot commands, like !whoami

                ##################
                # Admin commands #
                ##################
                if char.is_admin != 0:
                    if message.content == '!test_celeb':
                        await self.celebrity_fight()
                        return
                    elif message.content == '!godsend':
                        await self.godsend()
                        return
                    elif message.content == '!random_challenge':
                        char = self.random_online_char()
                        await self.random_challenge(char)
                        return
                    elif message.content == '!test_calamity':
                        await self.calamity()
                        return
                    elif message.content == '!monster_attack':
                        await self.monster_attack()
                        return
                    elif message.content == '!test_cs':
                        simple = self.characters.chars[181563324599762944]
                        seiyria = self.characters.chars[122862594724855808]
                        await self.try_critical_strike(simple, seiyria)
                        return
                    elif message.content == '!test_id':
                        simple = self.characters.chars[181563324599762944]
                        seiyria = self.characters.chars[122862594724855808]
                        await self.try_item_drop(simple, seiyria)
                        return
                    elif message.content == '!test_itemdrop':
                        simple = self.characters.chars[181563324599762944]
                        await self.find_item(simple)
                        return
                    elif message.content == '!test_collision':
                        simple = self.characters.chars[181563324599762944]
                        seiyria = self.characters.chars[122862594724855808]
                        await self.collision_fight(simple, seiyria)
                        return
                    elif message.content == '!top5':
                        await self.topx(5)
                        return
                    elif message.content == '!hog':
                        await self.hand_of_god()
                        return
                    elif message.content == '!random_gold':
                        await self.random_gold()
                        return
                    elif message.content == '!reset':
                        # TODO: reset quest once quest implemented
                        # TODO: reset tournament if implemented and one is running
                        # TODO: clear team stats, once implemented
                        self.characters.zero()
                        await self.gamechan.send("** Game Reset! **")
                        return

                ###################
                # Member commands #
                ###################
                if message.content.startswith('!class '):
                    new_class = message.content.split(' ', 1)[1]
                    char.charclass = new_class
                    self.characters.update(char)
                    await message.reply(f"Your class was changed to '{new_class}'", mention_author=True)
                    return
                elif message.content.startswith('!gender ') or message.content.startswith('!sex '):
                    new_gender = message.content.split(' ', 1)[1]
                    char.sex = new_gender
                    self.characters.update(char)
                    await message.reply(f"Your gender was changed to '{new_gender}'", mention_author=True)
                    return
                elif message.content.startswith('!align '):
                    new_align = message.content.split(' ', 1)[1]
                    if new_align == 'g' or new_align == 'n' or new_align == 'e':
                        char.alignment = new_align
                        self.characters.update(char)
                        await message.reply(f"Your alignment was changed to '{new_align}'", mention_author=True)
                    else:
                        await message.reply(
                            f"Alignment can be 'g' for good, 'n' for neutral, or 'e' for evil.", mention_author=True
                        )
                    return
                elif message.content.startswith('!whoami'):
                    devmsg(f"{char.username} did whoami")
                    await message.reply(char.whoami())
                    return

                elif message.content.startswith('!'):
                    await message.channel.send('Unrecognized bot command, perhaps?')
                    devmsg(f"failed bot command: {message.content} with user roles: {message.author.roles!r}")
                else:
                    return

    async def on_message_edit(self, before, after):
        # devmsg(f'a message was edited from {before} to {after}')
        if before.channel.name != 'idlerpg':
            return
        old_length = len(before.content)
        new_length = len(after.content)
        difference = abs(old_length - new_length)
        if difference == 0:
            difference = 1
        char = self.characters.find(after.author)
        pen = self.penalize(char, 'message', difference)
        dur = self.duration(pen)
        await self.gamechan.send(f"Penalty of {dur} added to {char.username}'s timer for editing a message.")

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
        char = self.characters.find(message.author)
        pen = self.penalize(char, 'message', length)
        dur = self.duration(pen)
        await self.gamechan.send(f"Penalty of {dur} added to {char.username}'s timer for deleting a message.")

    async def set_player_roles(self, member):
        """
        Set the player's roles correctly
        :param member: Member object
        :return: None
        """
        if member.raw_status == 'idle':
            await member.remove_roles(
                self.role_online, self.role_dnd,
                reason="IdleRPG Role Status Adjustment"
            )
            await member.add_roles(
                self.role_idle,
                reason="IdleRPG Role Status Adjustment")
        elif member.raw_status == 'online':
            await member.remove_roles(
                self.role_idle, self.role_dnd,
                reason="IdleRPG Role Status Adjustment"
            )
            await member.add_roles(
                self.role_online,
                reason="IdleRPG Role Status Adjustment")
        elif member.raw_status == 'dnd':
            await member.remove_roles(
                self.role_idle, self.role_online,
                reason="IdleRPG Role Status Adjustment"
            )
            await member.add_roles(
                self.role_dnd,
                reason="IdleRPG Role Status Adjustment")
        else:
            await member.remove_roles(
                self.role_idle, self.role_online, self.role_dnd,
                reason="IdleRPG Role Status Adjustment"
            )


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
        # devmsg(f'member {before.name} updated profile')
        # TODO: Penalize
        pass

    async def on_user_update(self, before, after):
        #devmsg(f'user {before.name} updated profile')
        # TODO: Penalize
        pass

    async def on_member_ban(self, guild, user):
        devmsg(f'user {user} was banned from {guild}')
        # TODO: Penalize

    async def on_presence_update(self, member_before, member_after):
        name = member_before.global_name
        if name is None:
            name = member_before.name
        char = self.characters.find(member_after)
        username = char.username
        # devmsg(f'char: {character!r}')
        # devmsg(f'Member "{username}" updated presence')
        await self.set_player_roles(member_after)
        if member_before.raw_status != member_after.raw_status:
            bef = member_before.raw_status
            aft = member_after.raw_status
            if bef == 'offline':
                char.online = 1
                self.characters.update(char)
                level = char.level
                charclass = char.charclass
                guild = member_before.guild.name
                heshe = char.heshe(uppercase=1)
                dur = self.duration(char.next_ttl)
                await self.gamechan.send(f"{username}, the level {level} {charclass} is now online from **{guild}**. "
                                         f"{heshe} reaches level {level + 1} in {dur}.")
            else:
                if aft == 'offline':
                    char.online = 0
                    pen = self.penalize(char, 'status')
                    self.characters.update(char)
                    dur = self.duration(pen)
                    await self.gamechan.send(f"Penalty of {dur} added to {username}'s timer for going offline.")

        if member_before.activity is not None and member_after.activity is not None and member_before.activity.name != member_after.activity.name:
            bef = member_before.activity
            aft = member_after.activity
            devmsg(f'before activity: {bef!r}')
            devmsg(f'after  activity: {aft!r}')
            pen = self.penalize(char, 'activity')
            self.characters.update(char)
            dur = self.duration(pen)
            devmsg(f"pen({pen}) dur({dur})")

            # f"Penalty of {dur} added to {username}'s timer for activity change of '{bef}' to '{aft}'."
            # Before is an ActivityType.watching
            # After can be 'None'
            await self.gamechan.send(
                f"Penalty of {dur} added to {username}'s timer for activity change."
            )

        if char.online == 0:
            return

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

    ##################################################
    #                                                #
    #              Server Logic Above                #
    #               Game Logic Below                 #
    #                                                #
    ##################################################

    async def mainloop(self):
        """
        This is the function that keeps us moving
        :return: None
        """
        # devmsg('start')
        self.loop_started = True
        try:
            await self.rpcheck()
        except Exception as e:
            devmsg(f"Exception: {e}")

        # Wait self_clock seconds and start mainloop() over
        # devmsg('sleeping')
        await asyncio.sleep(self.self_clock)
        # devmsg('creating task')
        self.bg_task = self.loop.create_task(self.mainloop())
        # devmsg('ended')

    async def rpcheck(self):
        """
        The meat and bones of the whole operation. Well, excluding the event penalties.
        :return: None
        """
        # devmsg('start')
        # Get a list of online users
        online = self.characters.online()
        online_good = self.characters.online(alignment='g')
        online_evil = self.characters.online(alignment='e')
        # devmsg('got char lists')

        online_count = len(online)
        # If nobody is online, we have nothing to do
        if online_count == 0:
            devmsg('ended: nobody online')
            return
        # devmsg('checking randoms for general events')
        if randint(0, int(24 * 86400 / self.self_clock)) < online_count: await self.monster_hunt()
        if randint(0, int(20 * 86400 / self.self_clock)) < online_count: await self.hand_of_god()
        if randint(0, int(9  * 86400 / self.self_clock)) < online_count: await self.group_battle()
        if randint(0, int(9  * 86400 / self.self_clock)) < online_count: await self.team_battle()
        if randint(0, int(8  * 86400 / self.self_clock)) < online_count: await self.calamity()
        if randint(0, int(8  * 86400 / self.self_clock)) < online_count: await self.godsend()
        if randint(0, int(8  * 14400 / self.self_clock)) < online_count: await self.celebrity_fight()
        if randint(0, int(8  * 19400 / self.self_clock)) < online_count: await self.random_gold()
        if randint(0, int(8  * 43200 / self.self_clock)) < online_count: await self.monster_attack()

        # Do the following if at least 15% of the characters are online
        # devmsg('checking randoms for good/evil events')
        if online_count / len(self.characters.chars) > .15:
            if randint(0, int(8  * 86400 / self.self_clock)) < len(online_good): await self.random_steal()
            if randint(0, int(12 * 86400 / self.self_clock)) < len(online_evil): await self.evilness()
            if randint(0, int(12 * 86400 / self.self_clock)) < len(online_good): await self.goodness()
            if randint(0, int(20 * 86400 / self.self_clock)) < len(online_good): await self.godsend()

        # Always do the following
        await self.moveplayers()
        await self.process_items()

        # TODO: Quests
        # devmsg('todo: quests')

        # Hourly Tasks  (TODO: fact check 'Hourly')
        if self.rpreport and (self.rpreport % 3600 < self.oldrpreport % 3600):
            devmsg('doing hourly tasks')
            # Reseed random
            seed()
            # Show the Top 5 idlers
            await self.topx(5)
            # Announce the next tournament
            # TODO: await self.announce_next_tournament()

            # TODO: random_challenge, hourly, 15% of all players must be level 25+ irpg.pl:2643
            players = self.characters.online(levelplus=25)
            # 15% of online players must be level 25+
            if len(players) / len(online) > .15:
                char = self.random_online_char()
                await self.random_challenge(char)

        # Decrement next_ttl, level up, etc
        # devmsg('doing instant tasks')
        curtime = int(time.time())
        for char_id in self.characters.online():
            char = self.characters.chars[char_id]
            # devmsg(f'processing char {char}')
            delta = curtime - self.lasttime
            char.next_ttl -= delta
            char.idled += delta
            # devmsg(f"{char.username} ttl is {char.next_ttl}")
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
                devmsg('updated char in db')
                heshe = char.heshe(uppercase=1)
                devmsg(f"heshe: {heshe}")
                dur = self.duration(base_ttl)
                await self.gamechan.send(
                    f"{char.username}, {char.charclass}, has attained level {char.level}! "
                    f"{heshe} reaches level {nextlevel} in {dur}."
                )
                await self.find_item(char)
                await self.find_gold(char)
                await self.random_challenge(char)
                await self.monster_attack_player(char)
            self.characters.update(char)

        # self.characters.updatedb()
        self.oldrpreport = self.rpreport
        self.rpreport += curtime - self.lasttime
        self.lasttime = curtime

        # Tournaments
        # TODO: irpg.pl:2720
        # devmsg('ended')

    def random_online_char(self):
        """
        Pick a random online character
        :return: char
        """
        players = self.characters.online()
        if players is None:
            return
        return self.characters.chars[choice(players)]

    async def monster_attack(self) -> None:
        """
        Pit random player against a random monster
        :return: None
        """
        devmsg('start')
        char = self.random_online_char()
        if char is None:
            return
        await self.monster_attack_player(char)
        devmsg('ended')

    async def monster_attack_player(self, char) -> None:
        """
        Pit specified player against a random monster
        :param char: character
        :return: None
        """
        devmsg('start')
        (myroll, mysum, myshowsum, myshowtxt) = self.display_sums(char, align=True, hero=True, pots=True)
        gain = 12  # Default gain of 12%
        loss = 9   # Default loss of 9%
        # Default monster sum
        monster_sum = int((randint(0, 30) + 85) * mysum / 100)
        if randint(1,5) == 1:
            # Easy challenge, gain 7% lose 10%
            monster_sum = int((randint(0,20) + 30) * mysum / 100)
            gain = 7
            loss = 10
        elif randint(1, 5) == 1:
            # Hard challenge, gain 22% lose 5%
            monster_sum = int((randint(0, 20) + 150) * mysum / 100)
            gain = 22
            loss = 5

        if monster_sum < 1:
            monster_sum = 1
        monster_name = self.get_monster_name(monster_sum)
        monster_roll = randint(0, monster_sum)
        output = f"{myshowtxt} {myshowsum} has been set upon by a {monster_name} [{monster_roll}/{monster_sum}]"
        if myroll >= monster_roll:
            gain = int( gain * char.next_ttl / 100)
            char.fightwon(gain)
            dur = self.duration(gain)
            nextlevel = self.nextlevel(char)
            await self.gamechan.send(f"{output} and won! {dur} is removed from {char.username}'s clock. {nextlevel}")
        else:
            loss = int(loss * char.next_ttl / 100)
            char.fightlost(loss)
            dur = self.duration(loss)
            nextlevel = self.nextlevel(char)
            await self.gamechan.send(f"{output} and lost! {dur} is added to {char.username}'s clock. {nextlevel}")
        self.characters.update(char)
        devmsg('ended')

    @staticmethod
    def get_monster_name(target_monster_sum):
        """
        Get an appropriate monster name for the sum provided
        :param target_monster_sum: monster sum
        :return: monster name
        """
        monster_name = "Monster"
        mfile = open('monsters.txt', 'r')
        while True:
            mline = mfile.readline().rstrip()
            monster_sum, monster_name = mline.split(None, 1)
            if int(monster_sum) >= target_monster_sum:
                mfile.close()
                break
        return monster_name

    async def random_challenge(self, char1) -> None:
        """
        Pit argument player against random player.
        Happens on leveling up, and to one random person each hour.
        :param char1: Targeted Player
        :return: None
        """
        devmsg('start')
        max_level = char1.level + 10
        itemsum = char1.itemsum()
        min_sum   = itemsum * 0.85
        max_sum   = itemsum * 1.15
        opponents = self.characters.filter(online=1, levelminus=max_level, charsumplus=min_sum,
                                           charsumminus=max_sum, notnamed=char1.username)
        if len(opponents) == 0:
            await self.gamechan.send(f"{char1.username} issued a challenge, but nobody felt like being defeated.")
            return

        char2 = self.characters.chars[choice(opponents)]
        char1name = char1.username
        char2name = char2.username
        char1roll, char1sum, char1showsum, char1showtxt = self.display_sums(char1, align=True, hero=True, pots=True)
        char2roll, char2sum, char2showsum, char2showtxt = self.display_sums(char2, align=True, hero=True, pots=True)
        output = f"{char1showtxt} {char1showsum} has challenged {char2name} {char2showsum} in combat"
        if char1roll >= char2roll:
            # char1 wins
            gain = int(char2.level / 4)
            if gain < 7: gain = 7
            gain = int((gain / 100) * char1.next_ttl)
            dur = self.duration(gain)
            char1.fightwon(gain)  # ttl gain, battles won incremented
            char2.fightlost(0)  # they don't get penalized, but battles lost incremented
            nl = self.nextlevel(char1)
            await self.gamechan.send(f"{output} and won! {dur} is removed from {char1name}'s clock. {nl}")
            if char1sum > 0 and char2sum > 0 and char1roll / char1sum >= .85 and char2roll / char2sum <= .15:
                # Try critical strike
                dice = await self.try_critical_strike(char1, char2)
                if dice == 0:
                    # Try item drop if crit failed
                    await self.try_item_drop(char1, char2)
        else:
            gain = int(char2.level / 7)
            if gain < 7: gain = 7
            gain = int((gain / 100) * char1.next_ttl)
            dur = self.duration(gain)
            char1.fightlost(gain)
            char2.fightwon(0)
            nl = self.nextlevel(char1)
            await self.gamechan.send(f"{output} and lost! {dur} is added to {char1name}'s clock. {nl}")

        self.characters.update(char1)
        self.characters.update(char2)
        devmsg('ended')

    async def find_gold(self, char):
        devmsg('start')
        gold_amount = randint(0, char.level) + 6
        char.gold += gold_amount
        self.characters.update(char)
        gold_total = char.gold
        await self.gamechan.send(
            f"{char.username} found {gold_amount} gold pieces lying on the "
            f"ground and picked them up to sum {gold_total} total gold."
        )
        devmsg('ended')

    async def find_item(self, char):
        """
        character finds a random item
        :param char: character
        :return: None
        """
        devmsg('start')
        item_type = self.random_item()
        curr_level = char.get_item(item_type)
        HeShe = char.heshe(True)
        himher = char.himher()
        hisher = char.hisher()
        HisHer = char.hisher(True)
        raw_item = self.get_unique_item(char.level)
        if self.item_level(raw_item) == 0:
            # Random plain item
            devmsg('random plain item')
            if char.level > 50:
                item_level = char.level - 25 + randint(0, int(char.level / 2) + 25)
            else:
                half_level = int(char.level / 2)
                if half_level < 1:
                    half_level = 1
                min_level = randint(1, half_level)
                max_level = min_level + randint(0, int(char.level * 1.5))
                item_level = str(randint(min_level, min_level + max_level))
                devmsg(f'generated item level: {item_level}')
            curr_item = self.format_named_item(curr_level, item_type)
            new_item = self.format_named_item(item_level, item_type)
            output = f"{char.username} found a {new_item}"
            if self.item_level(item_level) > self.item_level(curr_level):
                # It is better
                devmsg('it is better')
                output += f"! {HisHer} current {item_type} was level {curr_level}, so it seems Luck is with {himher}!"
                self.drop_item(char, item_type, curr_level)
                char.set_item(item_type, item_level)
            else:
                devmsg('it is worse')
                # Worse, or same, drop it
                action = f"{HeShe} drops it on the ground."
                if char.engineer:
                    action = f"{HeShe} gives it to {hisher} Engineer."
                output += f", but it wasn't better than {hisher} {curr_item}. {action}"
                # TODO: engineer_item: irpg.pl:3440
                self.drop_item(char, item_type, item_level)  # TODO: unless engineer!!
            await self.gamechan.send(output)
        else:
            # Unique item
            # TODO: unique items, irpg.pl:3445
            devmsg('unique item, please make me work')

        self.characters.update(char)
        devmsg('ended')

    @staticmethod
    def random_item():
        item_type = choice(
            ['ring', 'amulet', 'charm', 'weapon', 'helm', 'tunic', 'gloves', 'legs', 'shield', 'boots']
        )
        return item_type

    def drop_item(self, char, item_type: str, item_level: str):
        """
        Drop an item on the map. This is where our dict of dicts of lists of dicts comes into play.
        :param char: object, character
        :param item_type: string, type of item
        :param item_level: string, describing item attributes
        :return: None
        """
        level = self.item_level(item_level)
        if level == 0:
            return
        x = char.x_pos
        y = char.y_pos
        map_item = {
            'type': item_type,
            'level': item_level,
            'last': time.time(),
        }
        if x in self.map_items:                         # Dict 1, x coord
            if y in self.map_items[x]:                  # Dict 2, y coord
                self.map_items[x][y].append(map_item)   # List of Dict 3s
            else:
                self.map_items[x][y] = [map_item]
        else:
            self.map_items[x] = {y: [map_item]}

    def format_named_item(self, item: str, item_type: str) -> str:
        """
        Format an item of a type
        :param item: string like '5' or 'a5' or '5a' or 'a5a'
        :param item_type: ring, amulet, etc.
        :return: formatted string describing the item
        """
        prefix, level, suffix = self.item_parse(item)
        devmsg(f"prefix({prefix}) level({level}) suffix({suffix})")
        name_item = f"level {level} "
        # TODO: Add affixes
        name_item += item_type
        return name_item

    @staticmethod
    def item_parse(item: str):
        """
        Split prefix, level, and suffix from raw item string
        :param item: string, item description
        :return: list of 1 char, 1 integer, 1 char
        """
        prefix = ''
        level = ''
        suffix = ''
        digits = '0123456789'
        alphas = 'abcdefghijklmnopqrstuvwxyz'
        stage = 0  # 0: prefix, 1: level, 2: suffix
        for x in item:
            if stage == 0 and x in alphas:
                prefix = x
                stage = 1
                continue
            elif stage == 0 and x in digits:
                level += x
                stage = 1
                continue
            elif stage == 1 and x in digits:
                level += x
                continue
            elif stage == 1 and x in alphas:
                suffix = x
                stage = 2
        return [prefix, level, suffix]

    @staticmethod
    def item_level(item: str) -> int:
        """
        Strip 'unique' data from an item, returning just the level
        :param item: item string
        :return: integer level
        """
        devmsg('start')
        return int(
            item.translate(
                {ord(letter): None for letter in 'abcdefghijklmnopqrstuvwxyz'}
            )
        )

    def get_unique_item(self, level: int) -> str:
        devmsg('start')
        devmsg('TODO: Generate unique items!')
        devmsg('ended')
        return '0'

    def base_ttl(self, level: int) -> int:
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
        # devmsg('ended')
        pass

    async def moveplayers(self):
        # devmsg('start')
        if self.lasttime <= 1:
            return
        online_player_ids = self.characters.online()
        online_count = len(online_player_ids)
        if online_count == 0:
            return
        positions = {}  # nested dict to hold player positions to detect collisions
        # TODO: implement quest type 2
        for player_id in online_player_ids:
            char = self.characters.chars[player_id]
            # devmsg(f'moving player {char.username}')
            char.x_pos += randint(-1, 1)  # -1, 0, or 1
            char.y_pos += randint(-1, 1)  # So doesn't move, or just 1 spot in any direction
            if char.x_pos > self.mapx:
                char.x_pos -= self.mapx
            if char.y_pos > self.mapy:
                char.y_pos -= self.mapy
            if char.x_pos < 0:
                char.x_pos += self.mapx
            if char.y_pos < 0:
                char.y_pos += self.mapy
            self.characters.update(char)
            # Here we implement collisions between players using nested dicts
            x = char.x_pos
            y = char.y_pos
            if x not in positions:
                positions[x] = {y: {'c': char, 'b': False}}  # c: character ref, b: indicate if battle happened
            else:
                if y not in positions[x]:
                    positions[x][y] = {'c': char, 'b': False}
                else:
                    if positions[x][y]['b'] is False:
                        # collision
                        devmsg(f"collide: {char.username}, {positions[x][y]['c'].username}")
                        positions[x][y]['b'] = True
                        await self.collision_fight(char, positions[x][y]['c'])

            # TODO: pick up items lying around irpg.pl#3697

        # devmsg('ended')

    async def collision_fight(self, char1, char2):
        """
        This happens when people on the map meet each other
        :param char1: character object that moved to a spot
        :param char2: character object that was already there
        :return: None
        """
        # devmsg('start')
        (p1roll, p1sum, p1showsum, p1showtxt) = self.display_sums(char1, align=True, hero=False, pots=False)
        # devmsg(f"{p1roll}, {p1sum}, {p1showsum}, {p1showtxt}")
        (p2roll, p2sum, p2showsum, p2showtxt) = self.display_sums(char2, align=True, hero=False, pots=False)
        # devmsg(f"{p2roll}, {p2sum}, {p2showsum}, {p2showtxt}")
        output_text = f"{p1showtxt} {p1showsum} has come upon {char2.username} {p2showsum}"
        if p1roll >= p2roll:  # char1 won
            gain = int(char2.level / 4)
            if gain < 7:
                gain = 7
            gain = int((gain / 100) * char1.next_ttl)
            char1.fightwon(gain)
            char2.blost += 1
            dur = self.duration(gain)
            # Convoluted logic that I wrote years ago in Perl...
            if p1roll < 51 and p1sum > 299 and p2sum > 299:
                output_text += " and won!"
            elif p2roll + 300 < p1roll and p2sum > 299:
                output_text += f" and straight stomped them in combat! {char2.username} cries!"
            else:
                battle_message = randint(0, 2)
                if battle_message == 0:
                    output_text += " and wins!"
                elif battle_message == 1:
                    output_text += " and rocked it!"
                elif battle_message == 2:
                    output_text += " and gave 'em what was coming!"
            nl = self.nextlevel(char1)
            output_text += f"\n{dur} is removed from {char1.username}'s clock. {nl}"
            await self.gamechan.send(output_text)
            # Critical Strike chance if p1 rolled 85+% of max and p2 rolled 15-% theirs
            if p1sum > 0 and p2sum > 0 and p1roll / p1sum >= .85 and p2roll / p2sum <= .15:
                dice = await self.try_critical_strike(char1, char2)
                if dice is False:
                    await self.try_item_drop(char1, char2)
        else:  # char2 won
            gain = int(char2.level / 7)
            if gain < 7:
                gain = 7
            gain = int((gain / 100) * char1.next_ttl)
            char1.fightlost(gain)
            char2.bwon += 1
            dur = self.duration(gain)
            if p2roll < 51 and p1sum > 299 and p2sum > 299:
                output_text += " and loses!"
            elif p1roll + 300 < p2roll and p1sum > 299:
                output_text += f" and brought bronze weapons to an iron fight! {char1.username} cries."
            else:
                battle_message = randint(0, 2)
                if battle_message == 0:
                    output_text += " and got flexed on in combat!"
                elif battle_message == 1:
                    output_text += " and realized it was a bad decision!"
                elif battle_message == 2:
                    output_text += " and didn't wake up till the next morning!"
            nl = self.nextlevel(char1)
            output_text += f"\n{dur} is added to {char1.username}'s clock. {nl}"
            await self.gamechan.send(output_text)
            # Critical Strike chance if p2 rolled 85+% of max and p1 rolled 15-% theirs
            if p1sum > 0 and p2sum > 0 and p1roll / p1sum <= .15 and p2roll / p2sum >= .85:
                dice = await self.try_critical_strike(char2, char1)
                if dice is False:
                    await self.try_item_drop(char2, char1)
        self.characters.update(char1)
        self.characters.update(char2)
        # devmsg('ended')

    async def try_critical_strike(self, char1, char2):
        """
        Character 1 attempts a critical strike on Character 2
        :param char1: Character 1
        :param char2: Character 2
        :return: 0 on Fail, 1 on Success
        """
        devmsg('start')
        al = char1.alignment
        cs_factor = 35                # neutral has a standard 1/35 chance of critically striking
        if al == "g": cs_factor = 50  # good has a harder time of it
        if al == "e": cs_factor = 20  # evil does it easier
        targ = randint(1, cs_factor)
        return_value = 0
        # devmsg(f"targ is {targ} for cs factor {cs_factor}")
        if targ == 1:
            gain = int(randint(5, 25) / 100 * char2.next_ttl)
            char2.next_ttl += gain
            char2.badd += gain
            c1 = char1.username
            c2 = char2.username
            dur = self.duration(gain)
            c2nl = self.nextlevel(char2)
            await self.gamechan.send(
                f"{c1} has dealt {c2} a Critical Strike! {dur} is added to {c2}'s clock. {c2nl}"
            )
            self.characters.update(char2)
            return_value = 1

        devmsg('ended')
        return return_value

    async def try_item_drop(self, char1, char2):
        devmsg('start')
        if char1.level < 20:
            devmsg('ended: level too low')
            return
        randbase = 70  # 1 in 70 chance to even bother checking
        # Make it less likely for a low levels to steal from higher levels, and easier for higher to take from lower
        randbase += char2.level
        randbase -= char1.level

        # Undead more likely to get a drop, priest less likely
        if char1.alignment == "e": randbase -= 10
        if char1.alignment == "g": randbase += 10

        # Priests more likely to drop an item, undead less likely
        if char2.alignment == "g": randbase -= 10
        if char2.alignment == "e": randbase += 10

        if randint(1, randbase) == 1:
            itype = self.random_item()  # item type
            c1il = self.item_level(char1.get_item(itype))  # character 1 item level
            c2il = self.item_level(char2.get_item(itype))  # character 2 item level
            if c2il > c1il:  # if character 2 item level > character 1 item level
                c1hh = char1.hisher()
                c2hh = char2.hisher()
                c1n = char1.username
                c2n = char2.username
                await self.gamechan.send(
                    f"In the fierce battle, {c2n} dropped {c2hh} level {c2il} {itype}! "
                    f"{c1n} picks it up, tossing {c1hh} old level {c1il} {itype} to {c2n}."
                )
                tmp = char1.get_item(itype)  # store char1's item
                char1.set_item(itype, char2.get_item(itype))  # set char1's item to char2's item
                char2.set_item(itype, tmp)   # set char2's item to the stored value of char1's
                self.characters.update(char1)
                self.characters.update(char2)

        devmsg('ended')

    def display_sums(self, char, align: bool, hero: bool, pots: bool):
        """
        Generate some data needed for combat
        :param char:  character object
        :param align: consider alignment in sums
        :param hero:  consider hero in sums
        :param pots:  consider potions in sums
        :return: list: int random combat roll, int sum, str roll result, str action taken
        """
        char_sum = char.itemsum(align=align)

        roll = randint(1, char_sum) if char_sum > 0 else 0
        output_text = f"{char.username}"
        output_sum  = f"[{roll}/{char_sum}]"

        factor = 0
        attack_text = ""

        if hero and char.hero == 1:
            # add in hero display
            hisher = char.hisher()
            hlevel = char.hlevel
            output_text += f', with {hisher} level {hlevel} **Hero**'
            factor = (hlevel + 100 + 2) / 100  # 2% bonus per hero level, including level 0 hero
            char_sum = int(char_sum * factor)
            roll = int(roll * factor)
            output_sum = f"[{roll}/{char_sum}]"
        if pots:
            # Power potion
            if char.powerpots > 0 and char.powerload != 0:
                output_text += ' plus a power-potion'
                char_sum = int(char_sum * 1.1)
                roll = int(roll * 1.1)
                output_sum = f"[{roll}/{char_sum}]"
                char.powerpots -= 1
                if char.powerload > 0:
                    char.powerload -= 1
                # Copy back, save to db
                self.characters.update(char)
            # Luck potion
            if char.luckpots > 0 and char.luckload != 0:
                # Add in a luck potion (5% to 10% to roll, but not to sum)
                output_text += ' plus a luck-potion'
                luck = char_sum * randint(5, 10) / 100
                roll += luck
                if roll > char_sum:  # don't go over max
                    roll = char_sum
                output_sum = f"[{roll}/{char_sum}]"
                char.luckpots -= 1
                if char.luckload > 0:
                    char.luckload -= 1
                # Copy back, save to db
                self.characters.update(char)
        return [int(roll), int(char_sum), output_sum, output_text]

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

    async def random_gold(self):
        devmsg('start')
        char = self.random_online_char()
        if char is None:
            return
        gold_amount = randint(0, char.level) + 10
        gold = char.addgold(gold_amount)
        self.characters.update(char)
        await self.gamechan.send(
            f"{char.username} just walked by {gold_amount} gold pieces and picked them up to sum {gold} total gold."
        )
        devmsg('ended')

    async def celebrity_fight(self):
        """
        Pit a random player against a random fantasy celebrity
        :return: None
        """
        devmsg('start')
        char = self.random_online_char()
        if char is None:
            return
        celebs = {
            'Humpty Dumpty'         :  0,
            'Tweedledee'            :  0,
            'Tweedledum'            :  0,
            'Cheshire Cat'          :  1,
            'Oompa Loompa'          :  1,
            'Bilbo Baggins'         :  2,
            'Hermione Granger'      :  2,
            'Princess Buttercup'    :  2,
            'Frodo Baggins'         :  3,
            'Samwise Gamgee'        :  3,
            'Gollum'                :  4,
            'Circe'                 :  4,
            'Robin Hood'            :  5,
            'Harry Potter'          :  5,
            'Shrek'                 :  6,
            'Princess Fiona'        :  6,
            'Conan'                 :  7,
            'Harry Dresden'         :  7,
            'Captain Jack Sparrow'  :  7,
            'Medusa'                :  8,
            'King Arthur'           :  8,
            'Joan of Arc'           :  8,
            'Merlin'                :  9,
            'Richard Rahl'          :  9,
            'Van Helsing'           :  9,
            'Saruman'               : 10,
            'Belgarath'             : 10,
            'Dread Pirate Roberts'  : 10,
            'Severus Snape'         : 11,
            "Zeddicus Zu'l Zorander": 11,
            'Albus Dumbledore'      : 12,
            'Lord Voldemort'        : 13,
            'Gandalf the Grey'      : 15,
            'Elminster'             : 15,
        }
        celeb = choice(list(celebs.keys()))
        clevel = celebs[celeb]
        devmsg(f"player({char}) celeb({celeb}) clevel({clevel})")
        oppsum = 150 * (clevel + 1)
        (p1roll, p1sum, p1showsum, p1showtxt) = self.display_sums(char, align=True, hero=False, pots=False)
        opproll = randint(1, oppsum)
        output = f"{p1showtxt} {p1showsum} fights with the legendary {celeb} [{opproll}/{oppsum}] and"
        level = char.level
        gain = int(oppsum * (level / 10))
        dur = self.duration(gain)
        if p1roll >= opproll:
            char.fightwon(gain)
            char.addgold(10)
            nextlevel = self.nextlevel(char)
            await self.gamechan.send(
                f"{output} wins! {dur} removed from {char.username}'s time and 10 gold added. {nextlevel}"
            )
        else:
            char.fightlost(gain)
            nextlevel = self.nextlevel(char)
            await self.gamechan.send(f"{output} lost! {dur} added to {char.username}'s time. {nextlevel}")
        self.characters.update(char)
        devmsg('ended')

    async def godsend(self) -> None:
        """
        Bless the unworthy
        :return: None
        """
        devmsg('start')
        char = self.random_online_char()
        if char is None:
            return
        name = char.username
        if randint(1, 10) == 1:
            type = self.random_item()
            hisher = char.hisher()
            HisHer = char.hisher(uppercase=True)
            output = None
            if type == 'ring':
                output = f"Someone accidentally spilled some luck potion on {name}'s ring, " \
                         f"and it gained 10% effectiveness."
            elif type == 'amulet':
                output = f"{name}'s amulet was blessed by a passing cleric! {HisHer} amulet gains 10% effectiveness."
            elif type == 'charm':
                output = f"{name}'s charm at a bolt of lightning! {HisHer} charm gains 10% effectiveness."
            elif type == 'weapon':
                output = f"{name} sharpened the edge of {hisher} weapon! {HisHer} weapon gains 10% effectiveness."
            elif type == 'helm':
                output = f"{name} beat the dents out of {hisher} helm! {HisHer} helm is not 10% stronger."
            elif type == 'tunic':
                output = f"A magician cast a spell of Rigidity on {name}'s tunic! " \
                         f"{HisHer} tunic gains 10% effectiveness."
            elif type == 'gloves':
                output = f"{name} cleaned {hisher} gloves in the dishwasher. " \
                         f"{HisHer} gloves gain 10% effectiveness."
            elif type == 'legs':
                output = f"The local wizard imbued {name}'s pants with a Spirit of Fortitude! " \
                         f"{HisHer} pants gain 10% effectiveness."
            elif type == 'shield':
                output = f"{name} reinforced {hisher} shield with a dragon's scales! " \
                         f"{HisHer} shidle gains 10% effectiveness."
            elif type == 'boots':
                output = f"{name} stepped in some unicorn poo. It was gross to clean up, " \
                         f"but the boots are not 10% more effective."

            rawitem = char.get_item(type)
            prefix, level, suffix = self.item_parse(rawitem)
            newlevel = int(level * 1.1)
            char.set_item(type, f"{prefix}{newlevel}{suffix}")
            await self.gamechan.send(output)

        else:
            bonus = int(randint(4, 12) / 100 * char.next_ttl)
            # TODO: pull line from events file
            char.addttl(bonus * -1)
            dur = self.duration(bonus)
            nextlevel = self.nextlevel(char)
            nl = char.level + 1
            action = "GENERIC_ACTION"
            efile = open('events.txt', 'r')
            index = 0
            while True:
                eline = efile.readline().rstrip()
                if eline == "":
                    efile.close()
                    break
                e_type, flavor = eline.split(None, 1)
                if e_type == "G":
                    index += 1
                    random_number = uniform(0, index)
                    if random_number < 1:
                        action = flavor
            await self.gamechan.send(f"{name} {action}. This wondrous godsend has "
                                     f"accelerated them {dur} towards level {nl}. {nextlevel}")

        self.characters.update(char)

        devmsg('ended')

    async def calamity(self):
        """
        A random player suffers a little one
        :return: None
        """
        devmsg('start')
        char = self.random_online_char()
        if char is None:
            return
        name = char.username

        if randint(1, 20) == 1:
            type = self.random_item()
            hisher = char.hisher()
            HisHer = char.hisher(uppercase=True)
            output = None
            if type == 'ring':
                output = f"{name} dropped {hisher} ring down the sink! " \
                         f"{HisHer} ring lost 10% of its effectiveness when the plumber got it out."
            elif type == 'amulet':
                output = f"{name} fell, chipping the stone in {hisher} amulet! " \
                         f"{HisHer} amulet loses 10% of its effectiveness."
            elif type == 'charm':
                output = f"{name} slipped and dropped {hisher} charm in a dirty bog! " \
                         f"{HisHer} charm loses 10% of its effectiveness."
            elif type == 'weapon':
                output = f"{name} left {hisher} weapon out in the rain to rust! " \
                         f"{HisHer} weapon loses 10% of its effectiveness."
            elif type == 'helm':
                output = f"A bird pooped on {name}'s helm, causing it to lose 10% of its effectiveness. " \
                          "(It was a very large bird.)"
            elif type == 'tunic':
                output = f"{name} spilled a level 7 shrinking potion on {hisher} tunic! " \
                         f"{HisHer} tunic loses 10% of its effectiveness."
            elif type == 'gloves':
                output = f"{name} tried cleaning {hisher} gloves in the dishwasher. " \
                         f"{HisHer} gloves lose 10% of their effectiveness."
            elif type == 'legs':
                output = f"{name} burned a hole through {hisher} leggings while ironing them! " \
                         f"{HisHer} leggings lose 10% of their effectiveness."
            elif type == 'shield':
                output = f"{name}'s shield was damaged by a dragon's fiery breath! " \
                         f"{HisHer} shield loses 10% of its effectiveness."
            elif type == 'boots':
                output = f"{name} stepped on a really sharp rusty nail. " \
                         f"{HisHer} boots lost 10% of their effectiveness."

            rawitem = char.get_item(type)
            prefix, level, suffix = self.item_parse(rawitem)
            newlevel = int(level * 0.9)
            char.set_item(type, f"{prefix}{newlevel}{suffix}")
            await self.gamechan.send(output)

        else:
            penalty = int(randint(4, 12) / 100 * char.next_ttl)
            # TODO: pull line from events file
            char.addttl(penalty)
            dur = self.duration(penalty)
            nextlevel = self.nextlevel(char)
            nl = char.level + 1
            action = "GENERIC_CALAMITY"
            efile = open('events.txt', 'r')
            index = 0
            while True:
                eline = efile.readline().rstrip()
                if eline == "":
                    efile.close()
                    break
                e_type, flavor = eline.split(None, 1)
                if e_type == "C":
                    index += 1
                    random_number = uniform(0, index)
                    if random_number < 1:
                        action = flavor

            await self.gamechan.send(
                f"{name} {action}. This terrible calamity has slowed them {dur} from level {nl}. {nextlevel}"
            )

        self.characters.update(char)

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
        # await self.gamechan.send(f"TODO: Hand of God!")
        char = self.random_online_char()
        if char is None:
            return
        win = randint(0, 4)
        bonus = int(randint(4, 75) / 100 * char.next_ttl)
        dur = self.duration(bonus)
        nl = char.level + 1
        if win:
            char.next_ttl -= bonus
            nextlevel = self.nextlevel(char)
            await self.gamechan.send(f"Verily I say unto thee, the Heavens have burst forth, and the "
                                     f"blessed hand of God carried {char.username} {dur} forward. {nextlevel}")
        else:
            char.next_ttl += bonus
            nextlevel = self.nextlevel(char)
            await self.gamechan.send(f"Thereupon He stretched out His little finger among them and consumed "
                                     f"{char.username} with fire, slowing the heathen by {dur}. {nextlevel}")
        self.characters.update(char)
        devmsg('ended')

    def nextlevel(self, char):
        next_level = char.level + 1
        dur = self.duration(char.next_ttl)
        return f"{char.username} reaches level {next_level} in {dur}."

    async def monster_hunt(self):
        devmsg('start')
        await self.gamechan.send(f"TODO: Monster Hunt!")
        devmsg('ended')

    async def topx(self, count=5):
        chars = await self.characters.topx(count)
        lines = [f'Idle RPG Top {count} Players:']
        x = 1
        for char in chars:
            dur = self.duration(char.next_ttl)
            level = char.level
            charclass = char.charclass
            lines.append(f"{char.username}, the level {level} {charclass}, is #{x}! Next level in {dur}.")
            x += 1
        await self.gamechan.send('\n'.join(lines))

    def penalize(self, char, pen_type: str, *args) -> int:
        """
        Penalize a character for non-idle activities
        :param char: Character object
        :param pen_type: penalty type
        :param args: Various other args some types need
        :return: count of seconds penalized
        """
        # get local copy of character
        penalty_ttl = self.penttl(char.level)
        if pen_type == "status" or pen_type == "activity":
            # devmsg(f"{character} gets '{pen_type}' penalty")
            pen = int(30 * penalty_ttl / self.rpbase)
            if pen > self.limitpen:
                pen = self.limitpen
            # TODO: pen_nick is legacy from IRC. Make new counters for pen_status and pen_activity
            char.pen_nick += pen
            char.next_ttl += pen
            self.characters.update(char)
            return pen
        elif pen_type == "message":
            length = args[0]
            penalty_ttl = math.pow(self.rppenstep, char.level)
            pen = int(length * penalty_ttl)
            if pen > self.limitpen:
                pen = self.limitpen
            char.pen_msg += pen
            char.next_ttl += pen
            self.characters.update(char)
            return pen
        else:
            devmsg(f"{char.username} gets an unhandled '{pen_type}' penalty")
            return 600

    def penttl(self, level, ignore_level=False):
        """
        Calculate the magnitude of a penalty in ttl
        :param level: character's level
        :param ignore_level: choose to ignore level 60 adjustment
        :return: amount of seconds to penalize
        """
        if level <= 60 or ignore_level is True:
            return self.rpbase * math.pow(self.rppenstep, level)
        else:
            return (self.rpbase * math.pow(self.rppenstep, 60)) + (86400 * (level - 60))

    @staticmethod
    def duration(seconds):
        """
        :param seconds: a count of seconds
        :return: human-readable string of the duration of said seconds
        """
        second  = 1
        minute  = second * 60
        hour    = minute * 60
        day     = hour * 24
        year    = day * 365
        decade  = year * 10
        century = decade * 10
        sections = []
        # Optional sections
        if seconds >= century:
            centuries = math.trunc(seconds / century)
            if centuries == 1:
                sections.append("1 century")
            else:
                sections.append(f"{centuries} centuries")
            seconds -= centuries * century
        if seconds >= decade:
            decades = math.trunc(seconds / decade)
            if decades == 1:
                sections.append("1 decade")
            else:
                sections.append(f"{decades} decades")
            seconds -= decades * decade
        if seconds >= year:
            years = math.trunc(seconds / year)
            if years == 1:
                sections.append("1 year")
            else:
                sections.append(f"{years} years")
            seconds -= years * year
        # Required sections
        sections.append('%d day%s, %02d:%02d:%02d' % (
            seconds / day,
            '' if math.trunc(seconds / day) == 1 else 's',
            (seconds %   day) / hour,
            (seconds %  hour) / minute,
            (seconds %  minute)
        ))
        return ", ".join(sections)

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


# Set up Discord
my_intents = discord.Intents.all()
devmsg('instantiating game')
game = IdleRPG(intents=my_intents)

loop = asyncio.get_event_loop()
app = Quart(__name__)

navigation = {
    'Game Info': '/',
    'Player Info': '/players.html',
    'Contact': '/contact.html',
    'Source': 'https://idlerpg.net/source.php',
    'Other IRPGs': 'https://idlerpg.net/others.php',
    'Site Source': 'https://idlerpg.net/sitesource.php',
    'World Map': '/worldmap.html',
    'Quest Info': '/quest.html',
}


@app.route("/", methods=['GET'])
async def index():
    # return FileResponse('static/index.html', media_type='text/html')
    pagedict = {
        "navigation": navigation,
        "title": "Game Info",
    }
    return await render_template("index.html", context=pagedict)


@app.route("/players.html", methods=['GET'])
async def players():
    pagedict = {
        "navigation": navigation,
        "title": "Player Info",
        "characters": await game.characters.topx(None),
    }
    return await render_template(template_name_or_list="players.html", context=pagedict)


@app.route("/jon", methods=['GET'])
async def jon():
    base = (
        "<!DOCTYPE html>\n"
        "<html>\n"
        "  <head>\n"
        "    <title>Jon</title>\n"
        "    <link rel='icon' type='image/x-icon' href='/static/favicon.ico'>\n"
        "  </head>\n"
        "  <body>\n"
        "    <h1>Players</h1>\n"
        "    <h2>Pick a player to view</h2>\n"
        "    <p class='small'>[gray=offline]</p>\n"
        "    <ol>\n"
    )
    charlist = await game.characters.topx(None)
    for char in charlist:
        offline = ""
        if char.online is False:
            offline = " class='offline'"
        base += f"      <li{offline}>\n"
        base += f"        <a{offline} href='playerview.html/{char.id}'>{char.username}</a>,\n"
        base += f"        the level {char.level} {char.charclass}.\n"
        base += f"        Next level in {char.next_level_duration()}.\n"
        base += "      </li>\n"
    base += (
        "    </ol>\n"
        "    <p>See player stats in <a href='db.html'>table format</a>.</p>\n"
        "  </body>\n"
        "</html>\n"
    )
    return base


@app.route("/db.html", methods=['GET'])
async def db():
    chars = game.characters.webchars()
    pagedict = {
        "request": request,
        "navigation": navigation,
        "title": "Db-style Player Listing",
        "characters": chars,
        "rows": len(chars),
    }
    return await render_template(template_name_or_list="db.html", context=pagedict)


@app.route("/playerview.html/<int:player_id>", methods=['GET'])
async def playerview(player_id: int):
    char = game.characters.find(player_id=player_id)
    pagedict = {
        "navigation": navigation,
        "title": "Player Info: " + char.username,
        "character": char,
    }
    return await render_template(template_name_or_list="playerview.html", context=pagedict)


def main():
    devmsg('creating task for discord bot...')
    loop.create_task(game.start(os.getenv('DISCORD_TOKEN')))
    devmsg('creating task for web server...')
    loop.create_task(app.run_task(debug=True, host="127.0.0.1", port="80"))
    devmsg('OOPS')
    loop.run_forever()


devmsg(f"Name: {__name__}")
if __name__ == '__main__':
    # Start the Discord bot in a separate loop from Flask
    devmsg('starting?')
    main()
    devmsg('ended?')
