import sys; sys.path.insert(0,'/home/user/SMB-decomp/tools')
from dis6502 import *
d=open('/home/user/SMB-decomp/rom/game.nes','rb').read()
def bank(n): return d[16+n*16384:16+(n+1)*16384]
def dis(b,base,start,end):
    pc=start
    while pc<end:
        o=b[pc-base]
        if o not in OPS: print(f"{pc:04X} .db {o:02X}"); pc+=1; continue
        mn,m=OPS[o]; l=LEN[m]; by=b[pc-base:pc-base+l]
        v=int.from_bytes(by[1:],'little') if l>1 else 0
        if m=='rel': v=pc+2+(v-256 if v>127 else v)
        print(f"{pc:04X} {by.hex():8} {mn} {m} ${v:04X}" if l>1 else f"{pc:04X} {by.hex():8} {mn}")
        pc+=l
if __name__=="__main__":
    n=int(sys.argv[1]); s=int(sys.argv[2],16); e=int(sys.argv[3],16)
    dis(bank(n), 0xC000 if n==7 else 0x8000, s, e)
