"""
This file contains all the necessary bits to manage list of game characters
"""
import character
import time
from devmsg import devmsg
from operator import attrgetter


class Characters:
    """
    The Character object manager
    """
    def __init__(self, dbh):
        self.chars = {}  # Dict of char names to Character objects
        self.dbh = dbh

    def add(self, char_data):
        """
        Add a character to the list of known characters based on the character data
        :param char_data: Dict of character key/values
        :return: Character object
        """
        username = char_data["username"]
        char_id = char_data["id"]
        if username in self.chars:
            raise Exception(f"Character '{username}' already exists!")
        char = character.Character(char_data)
        self.chars[char_id] = char
        return char

    def find(self, member=None, player_id=None):
        """
        :param member: Discord member object
        :param player_id: player's id (same as Discord member id)
        :return: character object (existing, or new if it didn't exist)
        """
        if member is None and player_id is None:
            devmsg('you must provide either member object or player id')
            return
        if player_id is None:
            player_id = member.id
        if player_id in self.chars:
            return self.chars[player_id]
        # They don't exist, so we'll just add them right in against their will, possibly
        name = member.global_name
        if name is None:
            name = member.name
        online = 1 if member.status == 'online' else 0
        now = str(int(time.time()))
        chardict = {
            'id': player_id,
            'username': name,
            'password': '',
            'is_admin': 0,
            'level': 0,
            'charclass': 'IdleRPG Player',
            'next_ttl': 600, # rpbase
            'nick': name,
            'userhost': player_id,
            'online': online,
            'idled': 0,
            'x_pos': 0,
            'y_pos': 0,
            'pen_msg': 0,
            'pen_nick': 0,
            'pen_part': 0,
            'pen_kick': 0,
            'pen_quit': 0,
            'pen_quest': 0,
            'pen_logout': 0,
            'created': now,
            'lastlogin': now,
            'amulet': 0,
            'charm': 0,
            'helm': 0,
            'boots': 0,
            'gloves': 0,
            'ring': 0,
            'legs': 0,
            'shield': 0,
            'tunic': 0,
            'weapon': 0,
            'alignment': 'n',
            'gold': 0,
            'powerpots': 0,
            'ffight': 0,
            'bwon': 0,
            'blost': 0,
            'badd': 0,
            'bminus': 0,
            'avatar': 'not set',
            'sex': 'not set',
            'age': 'not set',
            'location': 'not set',
            'email': 'not set',
            'regentm': 0,
            'challengetime': 0,
            'hero': 0,
            'hlevel': 0,
            'slaytime': 0,
            'bet': 0,
            'pot': 0,
            'engineer': 0,
            'englevel': 0,
            'network': member.guild.name,
            'luckpots': 0,
            'bank': 0,
            'luckload': -1,
            'powerload': -1,
            'team': None,
            'rname': 'not set'
        }
        char = self.add(chardict)
        self.update(player_id)
        return char

    def load(self):
        """
        Load all the characters from the database
        :return: None
        """
        devmsg('loading...')
        cursor = self.dbh.cursor()
        rows = cursor.execute("select * from characters")
        cols = [x[0] for x in cursor.description]
        colcount = len(cols)
        for row in rows:
            chardict = {}
            for index in range(0, colcount):
                # devmsg(f"{cols[index]}: {row[index]}")
                chardict[cols[index]] = row[index]
            char = self.add(chardict)
            # devmsg(f"char: {char}")
        cursor.close()
        devmsg('loaded.')

    def updatedb(self):
        """
        Save every character to the database
        :return: None
        """
        for char_id in self.chars:
            self.update(char_id)
        # devmsg('updated whole db')

    def zero(self):
        for char in self.chars.values():
            char.level = 0
            char.next_ttl = 600
            char.idled = 0
            char.pen_msg = 0
            char.pen_nick = 0
            char.pen_part = 0
            char.pen_kick = 0
            char.pen_quit = 0
            char.pen_quest = 0
            char.pen_logout = 0
            char.amulet = '0'
            char.charm = '0'
            char.helm = '0'
            char.boots = '0'
            char.gloves = '0'
            char.ring = '0'
            char.legs = '0'
            char.shield = '0'
            char.tunic = '0'
            char.weapon = '0'
            char.powerpots = 0
            char.luckpots = 0
            char.alignment = 'n'
            char.gold = 0
            char.ffight = 0
            char.bwon = 0
            char.blost = 0
            char.badd = 0
            char.bminus = 0
            char.regentm = 0
            char.challengetime = 0
            char.hero = 0
            char.hlevel = 0
            char.engineer = 0
            char.englevel = 0
            char.slaytime = 0
            char.bet = 0
            char.pot = 0
            char.bank = 0
            self.update(char)

    def update(self, c) -> None:
        """
        Save a character object back to the database
        :param c: Character object
        :return: None
        """
        cursor = self.dbh.cursor()
        query = f"""replace into characters (
            password, is_admin,  level,    next_ttl, nick,     userhost,      online,     idled,     x_pos,     y_pos,     -- 10
            pen_msg,  pen_nick,  pen_part, pen_kick, pen_quit, pen_quest,     pen_logout, created,   lastlogin, amulet,    -- 20
            charm,    helm,      boots,    gloves,   ring,     legs,          shield,     tunic,     weapon,    powerpots, -- 30
            luckpots, alignment, gold,     ffight,   bwon,     blost,         badd,       bminus,    rname,     avatar,    -- 40
            sex,      age,       location, email,    regentm,  challengetime, hero,       hlevel,    engineer,  englevel,  -- 50
            slaytime, bet,       pot,      network,  bank,     team,          luckload,   powerload, id,        username,  -- 60
            charclass                                                                                                      -- 61
        ) values (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, -- 10
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, -- 20
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, -- 30
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, -- 40
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, -- 50
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, -- 60
            ?                             -- 61
        )"""
        cursor.execute(
            query,
            (
                c.password,      c.is_admin,   c.level,     c.next_ttl,  c.nick,       # 05
                c.userhost,      c.online,     c.idled,     c.x_pos,     c.y_pos,      # 10
                c.pen_msg,       c.pen_nick,   c.pen_part,  c.pen_kick,  c.pen_quit,   # 15
                c.pen_quest,     c.pen_logout, c.created,   c.lastlogin, c.amulet,     # 20
                c.charm,         c.helm,       c.boots,     c.gloves,    c.ring,       # 25
                c.legs,          c.shield,     c.tunic,     c.weapon,    c.powerpots,  # 30
                c.luckpots,      c.alignment,  c.gold,      c.ffight,    c.bwon,       # 35
                c.blost,         c.badd,       c.bminus,    c.rname,     c.avatar,     # 40
                c.sex,           c.age,        c.location,  c.email,     c.regentm,    # 45
                c.challengetime, c.hero,       c.hlevel,    c.engineer,  c.englevel,   # 50
                c.slaytime,      c.bet,        c.pot,       c.network,   c.bank,       # 55
                c.team,          c.luckload,   c.powerload, c.id,        c.username,   # 60
                c.charclass                                                            # 61
            )
        )
        cursor.close()
        self.dbh.commit()

    def filter(self, online: int = None, alignment: str = None, levelplus: int = None,
               levelminus: int = None, charsumplus: int = None, charsumminus: int = None,
               notnamed: str = None, debug: bool = False):
        """
        Get various lists of characters, with varying levels of specificity
        :param online:       Filter by online status
        :param alignment:    Filter by alignment
        :param levelplus:    Filter by char >= level
        :param levelminus:   Filter by char <= level
        :param charsumplus:  Filter by character itemsum >= charsum
        :param charsumminus: Filter by character itemsum <= charsum
        :param notnamed:     Filter by character username != notnamed
        :return: List of character IDs
        """
        char_list = []
        for c in self.chars:
            char = self.chars[c]
            u = char.username
            if online is not None and char.online != online:
                if debug: devmsg(f"{u} online disq: want {online} but {u} is {char.online}")
                continue
            if alignment is not None and char.alignment != alignment:
                if debug: devmsg(f"{u} align disq: want {alignment} but {u} is {char.alignment}")
                continue
            if levelplus is not None and char.level < levelplus:
                if debug: devmsg(f"{u} level < disq: want {levelplus}+ but {u} is {char.level}")
                continue
            if levelminus is not None and char.level > levelminus:
                if debug: devmsg(f"{u} level > disq: want {levelminus}- but {u} is {char.level}")
                continue
            if charsumplus is not None and char.itemsum() < charsumplus:
                if debug: devmsg(f"{u} sum < disq: want {charsumplus}+ but {u} is {char.itemsum()}")
                continue
            if charsumminus is not None and char.itemsum() > charsumminus:
                if debug: devmsg(f"{u} sum > disq: want {charsumminus}- but {u} is {char.itemsum()}")
                continue
            if notnamed is not None and char.username == notnamed:
                if debug: devmsg(f"{u} name disq: {char.username} == {notnamed}")
                continue
            char_list.append(c)
        return char_list

    def online(self, user_id: int = None, status: int = None, alignment: str = None,
               levelplus: int = None, levelminus: int = None):
        """
        Get a list of online users when no user or status specified
        :param user_id: Optional user id to check online status of
        :param status: Optional status to set a user to (user must be specified)
        :param alignment: Option alignment to filter the count. Cannot be used with user_id or status
        :param levelplus: Optional char >= level to filter the count. Cannot be used with user_id or status
        :param levelminus: Optional char <= level to filter the count. Cannot be used with user_id or status
        :return: List of IDs, or 0 or 1 for status get/set
        """
        # devmsg('start')
        if user_id is None:
            char_list = []
            for c in self.chars:
                char = self.chars[c]
                # devmsg(f"c: {c}")
                if char.online == 1:
                    char_list.append(c)
            # devmsg(f"ended: {char_list}")
            return char_list

        if alignment is not None:
            char_list = []
            for c in self.chars:
                char = self.chars[c]
                if char.online == 1 and char.alignment == alignment:
                    char_list.append(c)
            return char_list

        if levelplus is not None:
            char_list = []
            for c in self.chars:
                char = self.chars[c]
                if char.level >= levelplus:
                    char_list.append(c)
            return char_list

        if levelminus is not None:
            char_list = []
            for c in self.chars:
                char = self.chars[c]
                if char.level <= levelplus:
                    char_list.append(c)
            return char_list

        if status is None:
            return self.chars[user_id].online

        self.chars[user_id].online = status
        return status

    def topx(self, count=5):
        """
        Return the character objects, sorted by highest level and lowest ttl
        :param count: Limit the list to the top count, defaults to 5
        :return: list of character objects
        """
        timered = sorted(self.chars.values(), key=attrgetter('next_ttl'))
        leveled = sorted(timered, key=attrgetter('level'), reverse=True)
        return leveled[:count]


"""
sqlite3 database schema is as follows:

CREATE TABLE "CHARACTERS" (
	"id"	INTEGER NOT NULL UNIQUE,
	"username"	TEXT NOT NULL,
	"password"	TEXT NOT NULL,
	"is_admin"	INTEGER NOT NULL DEFAULT 0,
	"level"	INTEGER NOT NULL DEFAULT 0,
	"charclass"	TEXT NOT NULL,
	"next_ttl"	INTEGER NOT NULL DEFAULT 600,
	"nick"	TEXT,
	"userhost"	TEXT,
	"online"	INTEGER NOT NULL DEFAULT 0,
	"idled"	INTEGER NOT NULL DEFAULT 0,
	"x_pos"	INTEGER NOT NULL DEFAULT 0,
	"y_pos"	INTEGER NOT NULL DEFAULT 0,
	"pen_msg"	INTEGER NOT NULL DEFAULT 0,
	"pen_nick"	INTEGER NOT NULL DEFAULT 0,
	"pen_part"	INTEGER NOT NULL DEFAULT 0,
	"pen_kick"	INTEGER NOT NULL DEFAULT 0,
	"pen_quit"	INTEGER NOT NULL DEFAULT 0,
	"pen_quest"	INTEGER NOT NULL DEFAULT 0,
	"pen_logout"	INTEGER NOT NULL DEFAULT 0,
	"created"	INTEGER NOT NULL DEFAULT 0,
	"lastlogin"	INTEGER NOT NULL DEFAULT 0,
	"amulet"	TEXT NOT NULL DEFAULT '0',
	"charm"	TEXT NOT NULL DEFAULT '0',
	"helm"	TEXT NOT NULL DEFAULT '0',
	"boots"	TEXT NOT NULL DEFAULT '0',
	"gloves"	TEXT NOT NULL DEFAULT '0',
	"ring"	TEXT NOT NULL DEFAULT '0',
	"legs"	TEXT NOT NULL DEFAULT '0',
	"shield"	TEXT NOT NULL DEFAULT '0',
	"tunic"	TEXT NOT NULL DEFAULT '0',
	"weapon"	TEXT NOT NULL DEFAULT '0',
	"alignment"	TEXT NOT NULL DEFAULT 'n',
	"gold"	INTEGER NOT NULL DEFAULT 0,
	"powerpots"	INTEGER NOT NULL DEFAULT 0,
	"ffight"	INTEGER NOT NULL DEFAULT 0,
	"bwon"	INTEGER NOT NULL DEFAULT 0,
	"blost"	INTEGER NOT NULL DEFAULT 0,
	"badd"	INTEGER NOT NULL DEFAULT 0,
	"bminus"	INTEGER NOT NULL DEFAULT 0,
	"avatar"	TEXT NOT NULL DEFAULT 'not set',
	"sex"	TEXT NOT NULL DEFAULT 'not set',
	"age"	TEXT NOT NULL DEFAULT 'not set',
	"location"	TEXT NOT NULL DEFAULT 'not set',
	"email"	TEXT NOT NULL DEFAULT 'not set',
	"regentm"	INTEGER NOT NULL DEFAULT 0,
	"challengetime"	INTEGER NOT NULL DEFAULT 0,
	"hero"	INTEGER NOT NULL DEFAULT 0,
	"hlevel"	INTEGER NOT NULL DEFAULT 0,
	"slaytime"	INTEGER NOT NULL DEFAULT 0,
	"bet"	INTEGER NOT NULL DEFAULT 0,
	"pot"	INTEGER NOT NULL DEFAULT 0,
	"engineer"	INTEGER NOT NULL DEFAULT 0,
	"englevel"	INTEGER NOT NULL DEFAULT 0,
	"network"	TEXT DEFAULT NULL,
	"luckpots"	INTEGER NOT NULL DEFAULT 0,
	"bank"	INTEGER NOT NULL DEFAULT 0,
	"luckload"	INTEGER NOT NULL DEFAULT -1,
	"powerload"	INTEGER NOT NULL DEFAULT -1,
	"team"	INTEGER DEFAULT NULL,
	"rname" TEXT NOT NULL DEFAULT 'not set',
	PRIMARY KEY("id")
)
"""


if __name__ == "__main__":
    import sqlite3
    dbh = sqlite3.connect('irpg.db')
    characters = Characters(dbh)
    characters.load()
    charlist = characters.filter(debug=True, online=1, levelplus=5, levelminus=15)
    devmsg(f"charlist: {charlist}")