"""
This file contains all the things needed to manage a single character
"""
from devmsg import devmsg


class Character:
    def __init__(self, char_data):
        for key, val in char_data.items():
            # devmsg(f"setting '{key}' to '{val}'")
            setattr(self, key, val)
        # devmsg(f"char {vars(self)}")

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

