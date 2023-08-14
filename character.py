"""
This file contains all the things needed to manage a single character
"""
import math
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

    def heshe(self, uppercase=0):
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

    def hisher(self, uppercase=0):
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

    def himher(self, uppercase=0):
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

    def himselfherself(self, uppercase=0):
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
