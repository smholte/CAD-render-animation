"""Task 0258 (throw-away): a plain x k copy of a STEP file by changing its length unit (geometry untouched).
python scale_step.py in.step out.step k"""
import re, sys
src, dst, k = sys.argv[1], sys.argv[2], float(sys.argv[3])
t = open(src, encoding="latin-1").read()
mm = "( LENGTH_UNIT() NAMED_UNIT(*) SI_UNIT(.MILLI.,.METRE.) )"
n = t.count(mm)
new = "( CONVERSION_BASED_UNIT('SCALED',#9900002) LENGTH_UNIT() NAMED_UNIT(#9900003) )"
t = t.replace(mm, new)
extra = (f"#9900001 = {mm};\n#9900002 = LENGTH_MEASURE_WITH_UNIT(LENGTH_MEASURE({k!r}),#9900001);\n"
         "#9900003 = DIMENSIONAL_EXPONENTS(1.,0.,0.,0.,0.,0.,0.);\n")
i = t.rindex("ENDSEC;", 0, t.index("END-ISO"))
t = t[:i] + extra + t[i:]
open(dst, "w", encoding="latin-1").write(t)
print(f"{n} unit entries replaced")
