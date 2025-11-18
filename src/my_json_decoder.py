"""
This is actually for copying into RPython.
Simpler json decoder for the serialized format.
"""

class A: pass
jit = A()
jit.dont_look_inside = lambda a:a

class ListOrDictOrStr:
    LIST = 1
    DICT = 2
    STR = 3
    NONE = 4
    def __init__(self, ty, lst, dct, st):
        self.ty = ty
        self.lst = lst
        self.dct = dct
        self.st = st

    @jit.dont_look_inside
    def find_loop_id(self, id_str):
        if self.ty == ListOrDictOrStr.NONE:
            return ListOrDictOrStr(ListOrDictOrStr.NONE, [], {}, "")
        elif self.ty == ListOrDictOrStr.STR:
            return ListOrDictOrStr(ListOrDictOrStr.NONE, [], {}, "")
        elif self.ty == ListOrDictOrStr.DICT:
            for key, value in self.dct.items():
                assert key.ty == ListOrDictOrStr.STR
                if key.st[len("Trace:"):].strip() == id_str:
                    return value
                res = value.find_loop_id(id_str)
                if res.ty != ListOrDictOrStr.NONE:
                    return res
            return ListOrDictOrStr(ListOrDictOrStr.NONE, [], {}, "")
        elif self.ty == ListOrDictOrStr.LIST:
            for item in self.lst:
                res = item.find_loop_id(id_str)
                if res.ty != ListOrDictOrStr.NONE:
                    return res
            return ListOrDictOrStr(ListOrDictOrStr.NONE, [], {}, "")
        assert False
                

"""
This is actually for copying into RPython.
Simpler json decoder for the serialized format.
"""
class Decoder:
    def __init__(self, s):
        self.s = s
        self.pos = 0

    @jit.dont_look_inside
    def parse_array(self):
        assert self.s[self.pos] == '['
        self.pos += 1
        result = []
        while self.s[self.pos] != ']':
            result.append(self.parse_any())
            if self.s[self.pos] != ']':
                assert self.s[self.pos] == ','
                self.pos += 1
        assert self.s[self.pos] == ']'
        self.pos += 1
        return ListOrDictOrStr(ListOrDictOrStr.LIST, result, {}, "")

    @jit.dont_look_inside
    def parse_obj(self):
        assert self.s[self.pos] == '{'
        self.pos += 1
        key = self.parse_str()
        assert self.s[self.pos] == ':'
        self.pos += 1
        value = self.parse_any()
        assert self.s[self.pos] == '}'
        self.pos += 1
        return ListOrDictOrStr(ListOrDictOrStr.DICT, [], {key : value}, "")

    @jit.dont_look_inside
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
        return ListOrDictOrStr(ListOrDictOrStr.STR, [], {}, res)

    @jit.dont_look_inside
    def parse_null(self):
        assert self.s[self.pos] == 'n'
        self.pos += len("null")
        return ListOrDictOrStr(ListOrDictOrStr.NONE, [], {}, "")

    @jit.dont_look_inside
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
    print(Decoder(open("src/test/pyperformance/bm_go_guided_2_serialized").read()).parse_array())