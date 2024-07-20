"""
This file contains all the things needed to manage a single character
"""
import math
from datetime import datetime
from devmsg import devmsg


class Character:
    def __init__(self, char_data):
        for key, val in char_data.items():
            # devmsg(f"setting '{key}' to '{val}'")
            setattr(self, key, val)
        # devmsg(f"char {vars(self)}")

    def whoami(self):
        """
        Create a one-line description of the character
        :return: multiline string
        """
        al = self.alignment
        align = 'priest' if al == 'g' else 'evil' if al == 'e' else 'human'
        dur = self.duration(self.next_ttl)
        lev = self.level
        cls = self.charclass
        item_sum = self.itemsum()
        return (
            f"You are {self.username}, {align}, level {lev}, {cls}. Next level in {dur}.\n"
            f"Items: "
            f"ring[{self.ring}], "
            f"amulet[{self.amulet}], "
            f"charm[{self.charm}], "
            f"weapon[{self.weapon}], "
            f"helm[{self.helm}], "
            f"tunic[{self.tunic}], "
            f"gloves[{self.gloves}], "
            f"legs[{self.legs}], "
            f"shield[{self.shield}], "
            f"boots[{self.boots}], "
            f"Total sum: {item_sum}. "
            f"Gold: {self.gold}"
        )

    def addgold(self, amount):
        """
        Add arbitrary amount of gold to this character
        :param amount: Amount of gold to add
        :return: New gold amount on the character
        """
        self.gold += amount
        return self.gold

    def addttl(self, seconds) -> None:
        """
        Add (or remove if negative) some time to a character
        :param seconds: integer count of seconds
        :return: None
        """
        self.next_ttl += seconds

    def itemsum(self, align=False):
        """
        Return character's sum of items
        TODO: strip special item codes when implemented
        :param align: Whether to consider alignment
        :return: int
        """
        item_sum = int(self.ring) + int(self.amulet) + int(self.charm) + int(self.weapon) + int(self.helm)
        item_sum += int(self.tunic) + int(self.gloves) + int(self.legs) + int(self.shield) + int(self.boots)
        if align:
            if self.alignment == 'e':
                item_sum = int(item_sum * 0.9)
            if self.alignment == 'g':
                item_sum = int(item_sum * 1.1)
        return item_sum

    def heshe(self, uppercase: bool = 0):
        if self.sex == 'male':
            if uppercase:
                return 'He'
            return 'he'
        elif self.sex == 'female':
            if uppercase:
                return 'She'
            return 'she'
        elif self.sex == 'non-binary':
            if uppercase:
                return 'They'
            return 'they'
        else:
            if uppercase:
                return 'It'
            return 'it'

    def hisher(self, uppercase: bool = 0):
        if self.sex == 'male':
            if uppercase:
                return 'His'
            return 'his'
        elif self.sex == 'female':
            if uppercase:
                return 'Her'
            return 'her'
        elif self.sex == 'non-binary':
            if uppercase:
                return 'Their'
            return 'their'
        else:
            if uppercase:
                return 'Its'
            return 'its'

    def himher(self, uppercase: bool = 0):
        if self.sex == 'male':
            if uppercase:
                return 'Him'
            return 'him'
        elif self.sex == 'female':
            if uppercase:
                return 'Her'
            return 'her'
        elif self.sex == 'non-binary':
            if uppercase:
                return 'Them'
            return 'them'
        else:
            if uppercase:
                return 'It'
            return 'it'

    def himselfherself(self, uppercase: bool = 0):
        if self.sex == 'male':
            if uppercase:
                return 'Himself'
            return 'himself'
        elif self.sex == 'female':
            if uppercase:
                return 'Herself'
            return 'herself'
        elif self.sex == 'non-binary':
            if uppercase:
                return 'Theirself'
            return 'theirself'
        else:
            if uppercase:
                return 'Itself'
            return 'itself'

    def fightwon(self, gain):
        """
        Call this when a fight is won
        :param gain: ttl gained
        :return: None
        """
        self.next_ttl -= gain
        self.bminus += gain
        self.bwon += 1

    def fightlost(self, gain):
        """
        Call this when a fight is won
        :param gain: ttl gained
        :return: None
        """
        self.next_ttl += gain
        self.badd += gain
        self.blost += 1

    def get_item(self, item_type: str) -> str:
        """
        Get the level of a character's item
        :param item_type: the item type, amulet, shield...
        :return: string representing the item value
        """
        return getattr(self, item_type)

    def set_item(self, item_type: str, item_level: str) -> str:
        """
        Get the level of a character's item
        :param item_type: the item type, amulet, shield...
        :param item_level: the string description of the level (a2b, 12, etc.)
        :return: string representing the item value
        """
        return setattr(self, item_type, item_level)

    @staticmethod
    def duration(seconds):
        """
        :param seconds: a count of seconds
        :return: human-readable duration of said seconds
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

    def next_level_duration(self):
        """
        :return: human-readable string of the duration of next_ttl
        """
        return self.duration(self.next_ttl)

    def idled_duration(self):
        """
        :return: human-readable string of the total time this character has idled
        """
        return self.duration(self.idled)

    @staticmethod
    def timestamp(unixtime):
        """
        Convert unixtime to a date/time string
        :param unixtime: seconds since epoch
        :return: string representation of unixtime
        """
        return datetime.utcfromtimestamp(int(unixtime)).strftime('%c')
