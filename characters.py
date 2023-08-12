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
        devmsg(f"added character '{username}'")
        return char

    def find(self, member):
        """
        :param member: discord member object
        :return: character record or None
        """
        # cursor = self.dbh.cursor()
        # row = cursor.execute(f"select * from characters where id = {id}").fetchone()
        # cursor.close()
        # if row is None:
        #     return None
        # return row
        if member.id in self.chars:
            return self.chars[member.id]
        # They don't exist, so we'll just add them right in against their will, possibly
        name = member.global_name
        if name is None:
            name = member.name
        online = 1 if member.status == 'online' else 0
        now = str(int(time.time()))
        chardict = {
            'id': member.id,
            'username': name,
            'password': '',
            'is_admin': 0,
            'level': 0,
            'charclass': 'IdleRPG Player',
            'next_ttl': 600, # rpbase
            'nick': name,
            'userhost': member.id,
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
        self.update(member.id)
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
        devmsg('updated whole db')

    def update(self, character_id):
        """
        Save a character back to the database
        :param character_id: id of the character
        :return: None
        """
        devmsg('start')
        cursor = self.dbh.cursor()
        c = self.chars[character_id]
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
                c.team,          c.luckload,   c.powerload, character_id, c.username,  # 60
                c.charclass                                                            # 61
            )
        )
        # devmsg(f'lastrowid: {cursor.lastrowid}')
        cursor.close()
        self.dbh.commit()
        devmsg('ended')

    def online(self, user_id: int = None, status: int = None, alignment: str = None):
        """
        Get a list of online users when no user or status specified
        :param user_id: Optional user id to check online status of
        :param status: Optional status to set a user to (user must be specified)
        :param alignment: Option alignment to filter the count. Cannot be used with user_id or status
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

        if status is None:
            return self.chars[user_id].online

        self.chars[user_id].online = status
        # devmsg(f'ended: {status}')
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