"""
This is actually for copying into RPython.
Simpler json decoder for the serialized format.
"""

class Decoder:
    def __init__(self, s):
        self.s = s
        self.pos = 0

    def parse_array(self):
        assert self.s[self.pos] == '['
        self.pos += 1
        res = []
        while self.s[self.pos] != ']':
            res.append(self.parse_any())
            if self.s[self.pos] != ']':
                assert self.s[self.pos] == ','
                self.pos += 1
        assert self.s[self.pos] == ']'
        self.pos += 1
        return res

    def parse_obj(self):
        assert self.s[self.pos] == '{'
        self.pos += 1
        key = self.parse_str()
        assert self.s[self.pos] == ':'
        self.pos += 1
        value = self.parse_any()
        assert self.s[self.pos] == '}'
        self.pos += 1
        return {key : value}

    def parse_str(self):
        assert self.s[self.pos] == '"'
        self.pos += 1
        start = curr = self.pos
        while self.s[curr] != '"':
            curr += 1
        res = self.s[start:curr]
        self.pos = curr
        assert self.s[self.pos] == '"'
        self.pos += 1
        return res

    def parse_null(self):
        assert self.s[self.pos] == 'n'
        res = self.s[self.pos:self.pos + len("null")]
        self.pos += len("null")
        return res

    def parse_any(self):        
        nxt = self.s[self.pos]
        if nxt == '[':
            return self.parse_array()
        elif nxt == '{':
            return self.parse_obj()
        elif nxt == '"':
            return self.parse_str()
        elif nxt == 'n':
            return self.parse_null()
        print("Unrecognized token %d %s" % (self.pos, nxt))
        assert False
    


if __name__ == "__main__":
    print(Decoder(open("serialized").read()).parse_array())