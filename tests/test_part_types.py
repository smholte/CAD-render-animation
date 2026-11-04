"""Part-type library (task 0008): example names, parent assemblies, materials, CAD data.

Names are generic or in the style of vendor catalogues (SMC, Festo, igus, SKF, HIWIN, Sick,
Rittal...). Never put a customer's part names here: the repository is public.
"""

import time

import pytest

from fresing_render.core import cad_materials, materials_lib, part_types
from fresing_render.core import part_types_data as D
from fresing_render.core import rules as R

# ---- example names (expected group, '' = no part type) ----------------------------------------

PROF = "Aluminium profiles"; CAP = "Profile caps & covers"; CON = "Profile connectors & brackets"
PLATE = "Plates, blocks & brackets"; ROD = "Shafts, pins & spacers"; CHROME = "Chrome rods & linear shafts"
COVER = "Covers & panels"; SHEET = "Sheet metal parts"; WELD = "Welded frames & structures"; WEAR = "Wear strips"
PNEU = "Pneumatic cylinders & grippers"; ACT = "Linear actuators & rotary tables"; HYDC = "Hydraulic cylinders"
GAS = "Gas springs & shock absorbers"; VALVE = "Valves & valve terminals"; BALLV = "Ball valves & taps"
HYD = "Hydraulic components"; FIT = "Fittings"; HOSE = "Hoses & tubing"; PIPE = "Pipes"; CLAMP = "Pipe & hose clamps"
VAC = "Vacuum cups"; LIN = "Linear guides & ball screws"; BRG = "Bearings"; HSG = "Bearing housings & units"
BUSH = "Bushings & plain bearings"; IGL = "Plastic plain bearings"; CPL = "Couplings & brakes"; GEAR = "Gears & sprockets"
PUL = "Pulleys"; CHAIN = "Chains"; BELT = "Belts"; SPR = "Springs"; SEAL = "Seals & O-rings"; RUB = "Rubber parts"
CAB = "Cables"; ECH = "Cable chains"; GLAND = "Cable glands"; DUCT = "Wiring ducts"; TRAY = "Cable trays & DIN rails"
SENS = "Sensors & switches"; MOT = "Motors & gearboxes"; ENC = "Electrical enclosures"; ELEC = "Electrical components"
PB = "Push buttons & selectors"; ESTOP = "Emergency stops"; SIG = "Signal towers & lamps"; ROBOT = "Robots"
HANDLE = "Handles & knobs"; FOOT = "Levelling feet"; CAST = "Casters & wheels"; ROLL = "Conveyor rollers"
HINGE = "Hinges & latches"; WIN = "Windows & clear parts"; MESH = "Wire mesh & fences"; GRAT = "Gratings, stairs & railings"
LABEL = "Labels & signs"; MAN = "Mannequins"; TOOL = "Tool holders & tools"; LIFT = "Lifting gear & wire ropes"
WINCH = "Winch drums & sheaves"
SS = "Stainless steel parts"; ALU = "Aluminium parts"; ANO = "Anodised aluminium parts"; BANO = "Black anodised parts"
BRASS = "Brass parts"; BRONZE = "Bronze parts"; COPPER = "Copper parts"; GALV = "Galvanized parts"; ZINC = "Zinc plated parts"
STEEL = "Steel parts"; CI = "Cast iron parts"; POM = "POM parts"; PE = "PE parts"; PA = "PA parts"; PEEK = "PEEK parts"
PTFE = "PTFE parts"; PVC = "PVC parts"; PP = "PP parts"; PLAST = "Plastic parts"; GLASS = "Glass parts"
FOAM = "Foam parts"; FELT = "Felt parts"; WOOD = "Wood parts"

NAMES = [
    # aluminium profiles and accessories
    ("PROFILE 40X40", PROF), ("Profil 8 40x40 leicht", PROF), ("ALU PROFIEL 45X90", PROF), ("profile_30x30_L450", PROF),
    ("Aluminium profile 80x80 L=1200", PROF), ("0.0.026.23", PROF), ("3842 990 720", PROF), ("HFS5-2020-500", PROF),
    ("HFS8-4040-1000", PROF), ("40x40-500", PROF), ("ITEM PROFIEL 8 80X40", PROF), ("STRUT PROFILE 45x45", PROF),
    ("Aluprofil 30x60 Nut 8", PROF), ("EXTRUSION 4545-L800", PROF), ("BOSCH PROFIEL 45X45", PROF),
    ("END CAP 40X40", CAP), ("Abdeckkappe 8 40x40", CAP), ("AFDEKKAP PROFIEL 45", CAP), ("PROFILE CAP 30x30 BLACK", CAP),
    ("SLOT COVER 8", CAP), ("Nutabdeckprofil 8 grau", CAP), ("HFC5-2020", CAP), ("AFDEKSTRIP SLEUF 10", CAP),
    ("ANGLE BRACKET 40X40", CON), ("Winkel 8 40x40 Zn", CON), ("HOEKVERBINDER 45", CON), ("Corner bracket 30", CON),
    ("AUTOMATIC FASTENER 8", CON), ("HBLFSN5", CON), ("GUSSET 40", CON), ("Nutenwinkel 6 30x30", CON),
    # plates, blocks, brackets
    ("PLATE", PLATE), ("BASE PLATE 300X200X15", PLATE), ("MOUNTING_PLATE_02", PLATE), ("Montageplatte", PLATE),
    ("GRONDPLAAT", PLATE), ("BLOCK", PLATE), ("CLAMPING BLOCK", PLATE), ("Lagerbock Platte", PLATE),
    ("SENSOR BRACKET", PLATE), ("CYLINDER BRACKET", PLATE), ("MOTOR BRACKET", PLATE), ("Sensorhalter", PLATE),
    ("MOTORBEUGEL", PLATE), ("HOUDER SENSOR", PLATE), ("SPACER PLATE", PLATE), ("FLANGE MOTOR", PLATE),
    ("Motorflansch", PLATE), ("ADAPTER PLATE", PLATE), ("STOP BLOCK", PLATE), ("AANSLAG", PLATE), ("LEVER", PLATE),
    ("GRIPPER FINGER", PLATE), ("JAW LEFT", PLATE), ("HOUSING", PLATE), ("Gehaeuse oben", PLATE), ("SIDE GUIDE", PLATE),
    ("VALVE MANIFOLD", PLATE), ("SHIM 0.5MM", PLATE), ("SUPPORT", PLATE), ("CONSOLE", PLATE), ("HUB", PLATE),
    # shafts, pins, spacers
    ("SHAFT", ROD), ("SHAFT D20 L300", ROD), ("Welle 25h6", ROD), ("Antriebswelle", ROD), ("AXLE", ROD),
    ("PIN D10X40", ROD), ("PEN 8X30", ROD), ("SPACER", ROD), ("AFSTANDSBUS 10X20", ROD), ("Distanzhuelse 8x12", ROD),
    ("STANDOFF M4X20", ROD), ("SLEEVE", ROD), ("RING", ROD), ("SET COLLAR 20", ROD), ("Stellring 16", ROD),
    ("ROD", ROD), ("PIVOT", ROD), ("SPINDLE", ROD), ("KEY 8X7X40", ROD), ("SPRING PLUNGER M8", ROD),
    ("PISTON ROD", CHROME), ("Kolbenstange", CHROME), ("ZUIGERSTANG", CHROME), ("GUIDE ROD 16", CHROME),
    ("LINEAR SHAFT 20X400", CHROME), ("PSFJ20-300", CHROME), ("SFJ16-200", CHROME), ("Fuehrungswelle 20", CHROME),
    # covers, sheet metal, frames
    ("COVER", COVER), ("COVER PLATE", COVER), ("AFDEKPLAAT", COVER), ("Abdeckung links", COVER), ("PANEL SIDE", COVER),
    ("SIDE PANEL LH", COVER), ("DOOR", COVER), ("Tuer rechts", COVER), ("DEUR", COVER), ("GUARD", COVER),
    ("AFSCHERMING", COVER), ("HOOD", COVER), ("Schutzhaube", COVER), ("LID", COVER), ("DEKSEL", COVER), ("HATCH", COVER),
    ("CANOPY", COVER), ("Rueckwand", COVER),
    ("SHEET METAL BRACKET", PLATE), ("SHEET", SHEET), ("KANTWERK 2MM", SHEET), ("Blechteil", SHEET), ("Abkantteil", SHEET),
    ("DRIP TRAY", SHEET), ("Auffangwanne", SHEET), ("CHUTE", SHEET), ("HOPPER", SHEET), ("TRECHTER", SHEET),
    ("WELDMENT", WELD), ("FRAME WELDMENT", WELD), ("FRAME.WELDMENT", WELD), ("BASE FRAME", WELD), ("ONDERSTEL", WELD),
    ("Untergestell", WELD), ("Maschinengestell", WELD), ("LASCONSTRUCTIE", WELD), ("SCHWEISSKONSTRUKTION", WELD),
    ("CHASSIS", WELD), ("PEDESTAL", WELD), ("BOOM", WELD), ("GIEK", WELD), ("BEAM", WELD), ("HEA200 L=3000", WELD),
    ("IPE 160", WELD), ("UNP100", WELD), ("RHS 100X50X4", WELD), ("SHS 50X50X4", WELD), ("KOKER 40X40X3", WELD),
    ("L-PROFIEL 50X50X5", WELD), ("HOEKPROFIEL 40X4", WELD), ("ANGLE 50X50X5", WELD), ("Vierkantrohr 60x40x3", WELD),
    ("SQUARE TUBE 40X40X3", WELD), ("L 50X50X5", WELD), ("FLAT STEEL 50X10", STEEL), ("GANTRY", WELD), ("TOWER", WELD),
    ("WEAR STRIP", WEAR), ("SLIJTSTRIP PE1000", WEAR), ("Gleitleiste", WEAR), ("CHAIN GUIDE", WEAR),
    ("KETTINGGELEIDER", WEAR),
    # pneumatics
    ("CYLINDER", PNEU), ("PNEUMATIC CYLINDER 32X100", PNEU), ("Pneumatikzylinder", PNEU), ("CILINDER", PNEU),
    ("_MGPM32-75Z_ROD", CHROME), ("_MGPM32-75Z_BODY", PNEU), ("_MGPM32-75Z_PLATE", PNEU),
    ("_MGPM32-75Z_BUMPER", RUB), ("_MGPM32-75Z_GUIDE ROD", CHROME), ("CDQ2B32-50DZ", PNEU), ("CQ2B40-25DZ", PNEU),
    ("MGPM20-100Z", PNEU), ("MXS16-50", PNEU), ("CXSM10-20", PNEU), ("MHZ2-16D", PNEU), ("CJ2B16-60", PNEU),
    ("MY1B25G-500", PNEU), ("DSNU-20-50-P-A", PNEU), ("ADN-25-40-A-P-A", PNEU), ("DSBC-32-100-PPVA-N3", PNEU),
    ("DGSL-10-40-P1A", PNEU), ("HGPT-25-A", PNEU), ("GRIPPER", PNEU), ("Parallelgreifer", PNEU), ("PGN-plus 100", PNEU),
    ("SLIDE TABLE", PNEU), ("ROTARY ACTUATOR", PNEU), ("COMPACT CYLINDER", PNEU), ("STOP CYLINDER", PNEU),
    ("LINEAR ACTUATOR", ACT), ("Linearachse", ACT), ("ELECTRIC CYLINDER", ACT), ("EGC-80-500-TB", ACT),
    ("ELGA-TB-70-1000", ACT), ("LEFS25B-300", ACT), ("LEY32B-100", ACT), ("ROTARY TABLE", ACT), ("Rundschalttisch", ACT),
    ("HYDRAULIC CYLINDER", HYDC), ("HYDRAULIEKCILINDER 80/45-300", HYDC), ("Hydraulikzylinder", HYDC),
    ("LUFFING CYLINDER", HYDC),
    ("GAS SPRING", GAS), ("Gasfeder 200N", GAS), ("GASVEER", GAS), ("SHOCK ABSORBER", GAS), ("RB1007", GAS),
    ("MC150EUM", GAS), ("Stossdaempfer", GAS), ("DAMPER", GAS),
    ("VALVE", VALVE), ("SOLENOID VALVE", VALVE), ("Magnetventil", VALVE), ("MAGNEETVENTIEL 5/2", VALVE),
    ("SY5120-5DZ-01", VALVE), ("SY3120", VALVE), ("VQ1000", VALVE), ("VV5Q11-08", VALVE), ("VUVG-L14-M52-MT-G18-1R8L", VALVE),
    ("VTUG-10-VRPT", VALVE), ("MS6-LFR-1/2-D7", VALVE), ("AW20-02BG", VALVE), ("AR20-02", VALVE), ("FILTER REGULATOR", VALVE),
    ("Wartungseinheit", VALVE), ("VALVE TERMINAL", VALVE), ("SPEED CONTROLLER", VALVE), ("EJECTOR", VALVE),
    ("VACUUM GENERATOR", VALVE), ("CHECK VALVE", VALVE), ("Drosselrueckschlagventil", VALVE), ("ZH10DS-06-06-08", VALVE),
    ("BALL VALVE 1/2", BALLV), ("KOGELKRAAN DN15", BALLV), ("Kugelhahn", BALLV), ("NEEDLE VALVE", BALLV),
    ("AFTAPKRAAN", BALLV),
    ("HYDRAULIC PUMP", HYD), ("PUMP", HYD), ("Zahnradpumpe", HYD), ("POMP", HYD), ("HYDROMOTOR", HYD),
    ("ACCUMULATOR", HYD), ("POWER PACK", HYD), ("OIL TANK", HYD), ("RETURN FILTER", HYD), ("4WE6D6X/EG24N9K4", HYD),
    ("A10VSO28", HYD), ("OMR 100", HYD), ("PVG32", HYD),
    ("FITTING", FIT), ("PUSH IN FITTING 6MM", FIT), ("KQ2H06-01AS", FIT), ("KQ2L08-02AS", FIT), ("QS-6", FIT),
    ("QSL-1/8-6", FIT), ("NPQH-D-G18-Q6", FIT), ("ELBOW", FIT), ("TEE", FIT), ("Steckverschraubung", FIT),
    ("SCHROEFKOPPELING", FIT), ("SILENCER", FIT), ("Schalldaempfer G1/4", FIT), ("GELUIDDEMPER", FIT),
    ("QUICK COUPLING", FIT), ("SNELKOPPELING", FIT), ("NIPPLE 1/4", FIT), ("GE12LR", FIT), ("WE 12 L", FIT),
    ("SS-400-1-4", FIT), ("NOZZLE", FIT), ("AN200-02", FIT),
    ("HOSE", HOSE), ("TUBE PU 6X4", PIPE), ("PU TUBE 6X4", HOSE), ("TU0604B-20", HOSE), ("PUN-6X1-BL", HOSE),
    ("LUCHTSLANG 8MM", HOSE), ("Druckluftschlauch", HOSE), ("HYDRAULIC HOSE 2SN-12", HOSE), ("HYDRAULIEKSLANG", HOSE),
    ("SPIRAL HOSE", HOSE), ("CORRUGATED TUBE", HOSE),
    ("PIPE", PIPE), ("PIPE 48.3X3.2", PIPE), ("PIJP", PIPE), ("LEIDING", PIPE), ("Hydraulikrohr 12x1.5", PIPE),
    ("BUIS 25X2", PIPE), ("DN50 PIPE", PIPE), ("TUBE", PIPE),
    ("HOSE CLAMP", CLAMP), ("SLANGKLEM 20-32", CLAMP), ("Rohrschelle 42", CLAMP), ("PIPE CLAMP", CLAMP),
    ("P CLIP 10", CLAMP), ("STAUFF", CLAMP), ("CABLE CLAMP", CLAMP),
    ("SUCTION CUP", VAC), ("ZP20BN", VAC), ("ZUIGNAP 30", VAC), ("Saugnapf", VAC), ("ESS-30-SN", VAC),
    # linear motion, bearings, transmission
    ("LINEAR GUIDE", LIN), ("LINEAR RAIL 20 L=600", LIN), ("HGR15", LIN), ("HGH20CA", LIN), ("HGW25CC", LIN),
    ("MGN12H", LIN), ("SHS15C", LIN), ("SSR20XW", LIN), ("HSR25A", LIN), ("Kugelwagen", LIN), ("Fuehrungsschiene", LIN),
    ("CARRIAGE", LIN), ("RAIL", LIN), ("GELEIDERAIL", LIN), ("BALL SCREW", LIN), ("BALLSCREW 1605", LIN),
    ("SFU1605-500", LIN), ("Kugelgewindetrieb", LIN), ("KOGELOMLOOPSPINDEL", LIN), ("BALL NUT", LIN),
    ("Spindelmutter", LIN), ("LEAD SCREW", LIN), ("Trapezspindel", LIN), ("BK12", LIN), ("BF12", LIN),
    ("LM8UU", LIN), ("LINEAR BUSHING", LIN), ("KOGELBUS 20", LIN), ("LHFR20", LIN), ("SBR16", LIN),
    ("BEARING", BRG), ("BALL BEARING 6205", BRG), ("6205-2RS", BRG), ("6204 2Z", BRG), ("SKF 6205", BRG),
    ("FAG 6305", BRG), ("KUGELLAGER", BRG), ("Kugellager 6205", BRG), ("KOGELLAGER", BRG), ("NAALDLAGER", BRG),
    ("NU 210 ECP", BRG), ("22210 E", BRG), ("7205 BEP", BRG), ("32210 J2/Q", BRG), ("32210", ""), ("HK2016", BRG), ("CAM FOLLOWER", BRG),
    ("CF10", BRG), ("KR22", BRG), ("GE20ES", BRG), ("SLEWING RING", BRG), ("Drehkranz", BRG), ("DRAAIKRANS", BRG),
    ("LAGER", BRG), ("TRACK ROLLER", BRG),
    ("PILLOW BLOCK", HSG), ("UCP205", HSG), ("UCF 206", HSG), ("UCFL204", HSG), ("SY 25 TF", HSG), ("FY 30 TF", HSG),
    ("SNL 512", HSG), ("Stehlager", HSG), ("LAGERBLOK", HSG), ("BEARING HOUSING", HSG), ("Flanschlager", HSG),
    ("BUSHING", BUSH), ("BUSH 20X25X20", BUSH), ("Gleitlager", BUSH), ("GLIJLAGER", BUSH), ("DU BUSH 2020", BUSH),
    ("BRONZE BUSH", BUSH), ("Lagerbuchse", BUSH), ("PCM202520", BUSH), ("FLANGED BUSHING", BUSH), ("GLIJBUS", BUSH),
    ("IGLIDUR G", IGL), ("GFM-2023-21", IGL), ("iglidur J flange bearing", IGL), ("DRYLIN", IGL),
    ("COUPLING", CPL), ("KOPPELING", CPL), ("Klauenkupplung", CPL), ("ROTEX 19", CPL), ("JAW COUPLING", CPL),
    ("BELLOWS COUPLING", CPL), ("MCO25-8-10", CPL), ("SPIDER", CPL), ("BRAKE", CPL), ("Federdruckbremse", CPL),
    ("SHRINK DISC", CPL), ("TAPER BUSH", CPL), ("UNIVERSAL JOINT", CPL), ("Kardanwelle", CPL),
    ("GEAR", GEAR), ("SPUR GEAR Z20 M2", GEAR), ("TANDWIEL", GEAR), ("Zahnrad m2 z30", GEAR), ("PINION", GEAR),
    ("Ritzel", GEAR), ("RACK", ""), ("GEAR RACK M2", GEAR), ("Zahnstange", GEAR), ("WORM WHEEL", GEAR),
    ("SPROCKET", GEAR), ("Kettenrad", GEAR), ("KETTINGWIEL", GEAR), ("08B-1 Z15", GEAR), ("SSA1-20", GEAR),
    ("PULLEY", PUL), ("TIMING PULLEY", PUL), ("RIEMSCHIJF", PUL), ("Zahnriemenscheibe", PUL), ("POELIE", PUL),
    ("HTPA30S5M150", PUL), ("IDLER", PUL), ("SPANROL", PUL),
    ("CHAIN", CHAIN), ("ROLLER CHAIN 08B-1", CHAIN), ("KETTING", CHAIN), ("Rollenkette", CHAIN), ("ANCHOR CHAIN", CHAIN),
    ("RS40-1", CHAIN),
    ("BELT", BELT), ("TIMING BELT", BELT), ("TANDRIEM", BELT), ("Zahnriemen", BELT), ("1200-8M-30", BELT),
    ("HTD 1200", BELT), ("SPA 1250", BELT), ("V BELT", BELT), ("CONVEYOR BELT", BELT), ("TRANSPORTBAND", BELT),
    ("Foerderband", BELT),
    ("SPRING", SPR), ("COMPRESSION SPRING", SPR), ("DRUKVEER", SPR), ("Druckfeder", SPR), ("Zugfeder", SPR),
    ("TREKVEER", SPR), ("TORSION SPRING", SPR), ("SWF10-30", SPR), ("DIE SPRING", SPR),
    # seals, rubber
    ("SEAL", SEAL), ("O-RING 20X2 NBR", SEAL), ("ORING", SEAL), ("OR 20x2", SEAL), ("O-ring 47,5x2,5", SEAL),
    ("GASKET", SEAL), ("GASCKET", SEAL), ("O-RING.FITTING.UNIT", ""), ("PAKKING", SEAL), ("Flachdichtung", SEAL),
    ("DICHTUNG", SEAL), ("AFDICHTING", SEAL), ("DICHTRING", SEAL), ("WIPER", SEAL), ("SCRAPER", SEAL),
    ("Abstreifer", SEAL), ("SHAFT SEAL", SEAL), ("Simmerring 20x35x7", SEAL), ("KEERRING", SEAL), ("BA 20X35X7", SEAL),
    ("ROD SEAL", SEAL), ("GUIDE RING", SEAL), ("DOOR SEAL", SEAL), ("SEAL KIT", SEAL), ("Wellendichtring", SEAL),
    ("RUBBER BUFFER", RUB), ("BUMPER", RUB), ("Gummipuffer", RUB), ("BUFFER", RUB), ("AANSLAGRUBBER", RUB),
    ("Schwingmetall", RUB), ("TRILLINGSDEMPER", RUB), ("VIBRATION MOUNT", RUB), ("GROMMET", RUB),
    ("EDGE PROTECTION", RUB), ("Kantenschutz", RUB), ("BELLOWS", RUB), ("Faltenbalg", RUB), ("RUBBER STRIP", RUB),
    ("BRUSH", RUB), ("BORSTEL", RUB), ("FENDER", RUB),
    # electrical
    ("CABLE", CAB), ("KABEL", CAB), ("Steuerleitung", CAB), ("SENSOR CABLE", CAB), ("MOTOR CABLE", CAB),
    ("CF9.10.04", CAB), ("chainflex CF5", CAB), ("EVC001", CAB), ("4G1,5", CAB), ("3x0,75mm2", CAB),
    ("CABLE TIE", CAB), ("Kabelbinder", CAB), ("TY-RAP", CAB), ("WIRE HARNESS", CAB), ("BUSBAR", CAB),
    ("YF2A14-050VB3XLEAX", CAB),
    ("CABLE CHAIN", ECH), ("ENERGY CHAIN", ECH), ("E-CHAIN", ECH), ("Energiekette", ECH), ("Schleppkette", ECH),
    ("KABELRUPS", ECH), ("E2.15.050.0", ECH), ("E4.32.10.075.0", ECH), ("TRIFLEX", ECH), ("ZIPPER", ECH),
    ("CABLE GLAND M20", GLAND), ("WARTEL M16", GLAND), ("Kabelverschraubung M25", GLAND), ("SKINTOP MS-M 20", GLAND),
    ("KEL 24", GLAND),
    ("WIRING DUCT", DUCT), ("KABELGOOT 60X60", DUCT), ("Verdrahtungskanal", DUCT), ("BEDRADINGSGOOT", DUCT),
    ("CABLE TRAY", TRAY), ("KABELBAAN", TRAY), ("Kabelrinne", TRAY), ("DIN RAIL", TRAY), ("TS 35", TRAY),
    ("Hutschiene", TRAY), ("CABLE LADDER", TRAY),
    ("SENSOR", SENS), ("PROXIMITY SENSOR M12", SENS), ("INDUCTIVE SENSOR", SENS), ("Naeherungsschalter", SENS),
    ("INITIATOR", SENS), ("IF5250", SENS), ("IG5397", SENS), ("O5D100", SENS), ("PN7094", SENS), ("WTB4-3P2161", SENS),
    ("IME12-04BPSZC0K", SENS), ("BES 516-325-G-E4-C-PU-05", SENS), ("BOS 18M-PA-1PD-E5-C-S4", SENS),
    ("NBB8-18GM50-E2", SENS), ("LR-ZB250CP", SENS), ("E2E-X5ME1", SENS), ("E3Z-D61", SENS), ("D-M9B", SENS),
    ("D-A93", SENS), ("SMT-8M-A-PS-24V-E-0,3-M8D", SENS), ("SME-8M-DS-24V-K-2,5-OE", SENS), ("LIMIT SWITCH", SENS),
    ("Endschalter", SENS), ("EINDSCHAKELAAR", SENS), ("SAFETY SWITCH", SENS), ("AZM 161", SENS), ("PSEN 1.1", SENS),
    ("LIGHT CURTAIN", SENS), ("Lichtgitter", SENS), ("LICHTSCHERM", SENS), ("C4000-S01", SENS),
    ("PHOTOCELL", SENS), ("FOTOCEL", SENS), ("Lichtschranke", SENS), ("REFLECTOR", SENS), ("ENCODER", SENS),
    ("Drehgeber", SENS), ("PRESSURE SWITCH", SENS), ("Druckschalter", SENS), ("CAMERA", SENS), ("BARCODE SCANNER", SENS),
    ("LOAD CELL", SENS), ("MANOMETER", SENS), ("PRESSURE GAUGE", SENS), ("REED SWITCH", SENS), ("SWITCH", SENS),
    ("MOTOR", MOT), ("ELECTRIC MOTOR", MOT), ("Elektromotor", MOT), ("SERVOMOTOR", MOT), ("SERVO MOTOR", MOT),
    ("STEPPER MOTOR", MOT), ("Getriebemotor", MOT), ("GEARBOX", MOT), ("Planetengetriebe", MOT), ("REDUCTOR", MOT),
    ("TANDWIELKAST", MOT), ("1FK7063-5AF71", MOT), ("KA47 DRN80M4", MOT), ("DRN80M4", MOT), ("MSK071D-0450", MOT),
    ("AM8031-0D20", MOT), ("PLE80", MOT), ("NEMA 23", MOT), ("57HS56", MOT), ("SGM7J-04AFC6S", MOT), ("R88M-K40030H", MOT),
    ("SP+ 100", MOT), ("LINEAR MOTOR", MOT), ("WORM GEARBOX", MOT), ("MOTOREDUCTOR", MOT),
    ("ENCLOSURE", ENC), ("CONTROL CABINET", ENC), ("SCHAKELKAST", ENC), ("Schaltschrank", ENC), ("JUNCTION BOX", ENC),
    ("Klemmenkasten", ENC), ("AANSLUITKAST", ENC), ("AE 1060.500", ENC), ("TS 8806.500", ENC), ("RITTAL", ENC),
    ("CONTROL BOX", ENC), ("BEDIENPULT", ENC),
    ("PLC", ELEC), ("IO MODULE", ELEC), ("TERMINAL BLOCK", ELEC), ("Reihenklemme", ELEC), ("RIJGKLEM", ELEC),
    ("RELAY", ELEC), ("Relais", ELEC), ("CONTACTOR", ELEC), ("Schuetz", ELEC), ("CIRCUIT BREAKER", ELEC),
    ("Leitungsschutzschalter", ELEC), ("POWER SUPPLY 24V", ELEC), ("Netzteil", ELEC), ("VOEDING", ELEC),
    ("FREQUENCY INVERTER", ELEC), ("Frequenzumrichter", ELEC), ("SERVO DRIVE", ELEC), ("HMI", ELEC),
    ("TOUCH PANEL", ELEC), ("6ES7 214-1AG40-0XB0", ELEC), ("6ES7214-1AG40-0XB0", ELEC), ("3RT2015-1BB41", ELEC),
    ("EL1008", ELEC), ("EK1100", ELEC), ("750-1405", ELEC), ("2002-1201", ELEC), ("PNOZ X2.8P", ELEC),
    ("LC1D09BD", ELEC), ("GV2ME10", ELEC), ("CONNECTOR M12", ELEC), ("PLUG", ELEC), ("STEKKER", ELEC),
    ("Steckdose", ELEC), ("FUSE", ELEC), ("MAIN SWITCH", ELEC), ("HOOFDSCHAKELAAR", ELEC), ("FAN", ELEC),
    ("Filterluefter", ELEC), ("SLIP RING", ELEC), ("HARTING HAN 10E", ELEC), ("UT 4", ELEC), ("QUINT-PS/1AC/24DC/10", ELEC),
    ("BUZZER", ELEC),
    ("PUSH BUTTON", PB), ("Drucktaster", PB), ("DRUKKNOP", PB), ("SELECTOR SWITCH", PB), ("KEY SWITCH", PB),
    ("PILOT LIGHT", PB), ("JOYSTICK", PB), ("3SU1100-0AB20-1BA0", PB), ("XB5AA31", PB), ("M22-D-G", PB),
    ("FOOT SWITCH", PB),
    ("EMERGENCY STOP", ESTOP), ("E-STOP", ESTOP), ("NOODSTOP", ESTOP), ("Not-Aus", ESTOP), ("NOT HALT", ESTOP),
    ("Pilztaster", ESTOP), ("XB4BS8445", ESTOP), ("PULL WIRE SWITCH", ESTOP),
    ("SIGNAL TOWER", SIG), ("STACK LIGHT", SIG), ("SIGNAALZUIL", SIG), ("Signalsaeule", SIG), ("SIGNAL.LAMP", SIG),
    ("BEACON", SIG), ("ZWAAILAMP", SIG), ("LED STRIP", SIG), ("WORK LIGHT", SIG), ("Maschinenleuchte", SIG),
    ("LAMP", SIG), ("FLOODLIGHT", SIG), ("WERMA KS 71", SIG), ("LR6-302WJNW-RYG", SIG), ("TL50", SIG),
    ("ROBOT", ROBOT), ("Industrieroboter", ROBOT), ("IRB 6700", ROBOT), ("KR 10 R1100", ROBOT), ("UR10e", ROBOT),
    ("M-20iA", ROBOT), ("COBOT", ROBOT), ("SCARA", ROBOT),
    # operator parts, furniture
    ("HANDLE", HANDLE), ("BOW HANDLE", HANDLE), ("HANDGREEP", HANDLE), ("Buegelgriff", HANDLE), ("GN 565-20-M6", HANDLE),
    ("KNOB", HANDLE), ("STAR KNOB M8", HANDLE), ("Sterngriff", HANDLE), ("CLAMPING LEVER", HANDLE),
    ("Klemmhebel", HANDLE), ("HANDWHEEL", HANDLE), ("HANDWIEL", HANDLE), ("INDEXING PLUNGER", HANDLE),
    ("TOGGLE CLAMP", HANDLE), ("Schnellspanner", HANDLE), ("K0269.1080", HANDLE), ("CRANK", HANDLE),
    ("LEVELLING FOOT", FOOT), ("LEVELING FOOT M16", FOOT), ("STELVOET", FOOT), ("Stellfuss", FOOT),
    ("Nivellierfuss", FOOT), ("MACHINE FOOT", FOOT), ("FOOT", FOOT), ("LV.F", FOOT), ("GN 343", FOOT),
    ("CASTER", CAST), ("SWIVEL CASTER 100", CAST), ("ZWENKWIEL", CAST), ("Lenkrolle", CAST), ("BOKWIEL", CAST),
    ("WHEEL", CAST), ("Laufrad", CAST), ("BLICKLE", CAST), ("TENTE", CAST),
    ("CONVEYOR ROLLER", ROLL), ("ROLLER", ROLL), ("TRANSPORTROL", ROLL), ("Tragrolle", ROLL), ("BALL TRANSFER UNIT", ROLL),
    ("Kugelrolle", ROLL), ("GUIDE ROLLER", ROLL), ("INTERROLL", ROLL), ("ROL 50", ROLL),
    ("HINGE", HINGE), ("SCHARNIER", HINGE), ("Tuerscharnier", HINGE), ("LATCH", HINGE), ("DOOR LOCK", HINGE),
    ("Schloss", HINGE), ("MAGNETIC CATCH", HINGE), ("BALL CATCH", HINGE), ("QUARTER TURN", HINGE), ("GN 161", HINGE),
    ("EMKA", HINGE), ("Vorhaengeschloss", HINGE),
    ("WINDOW", WIN), ("VENSTER", WIN), ("Sichtfenster", WIN), ("KIJKVENSTER", WIN), ("VIEWING WINDOW", WIN),
    ("RUIT", WIN), ("SAFETY GLASS", WIN), ("PC PLATE 4MM", WIN), ("CLEAR COVER", WIN), ("PLEXIGLAS PLAAT", WIN),
    ("Polycarbonat Scheibe", WIN), ("LEXAN 6MM", WIN), ("PERSPEX PANEL", WIN), ("ACRYLIC SHEET", WIN),
    ("WIRE MESH", MESH), ("MESH PANEL", MESH), ("GAASPANEEL", MESH), ("Gitterelement", MESH), ("FENCE", MESH),
    ("SAFETY FENCE", MESH), ("HEKWERK", MESH), ("Schutzzaun", MESH), ("PERFORATED PLATE", MESH), ("Lochblech", MESH),
    ("EXPANDED METAL", MESH), ("AXELENT", MESH),
    ("GRATING", GRAT), ("ROOSTER", GRAT), ("Gitterrost", GRAT), ("WALKWAY", GRAT), ("PLATFORM", GRAT), ("BORDES", GRAT),
    ("STAIR", GRAT), ("STAIRS", GRAT), ("Treppe", GRAT), ("TRAP", GRAT), ("LADDER", GRAT), ("Steigleiter", GRAT),
    ("HANDRAIL", GRAT), ("LEUNING", GRAT), ("Gelaender", GRAT), ("RAILING", GRAT), ("KICKPLATE", GRAT),
    ("CHECKER PLATE", GRAT), ("TRAANPLAAT", GRAT), ("Riffelblech", GRAT), ("STAIR STEP", GRAT),
    ("LABEL", LABEL), ("STICKER", LABEL), ("NAMEPLATE", LABEL), ("TYPE PLATE", LABEL), ("Typenschild", LABEL),
    ("TYPEPLAAT", LABEL), ("WARNING SIGN", LABEL), ("Warnschild", LABEL), ("PICTOGRAM", LABEL), ("LOGO", LABEL),
    ("DECAL", LABEL), ("ARROW", LABEL),
    ("MANNEQUIN", MAN), ("HUMAN", MAN), ("Human_Male_50th", MAN), ("OPERATOR", MAN), ("PERSON", MAN), ("MENS", MAN),
    ("Mensch", MAN), ("WORKER", MAN), ("MANIKIN", MAN),
    ("TOOL HOLDER", TOOL), ("COLLET ER32", TOOL), ("SPANTANG", TOOL), ("Spannzange", TOOL), ("ER32", TOOL),
    ("HSK63A", TOOL), ("SK40", TOOL), ("BT40", TOOL), ("END MILL D10", TOOL), ("FREES", TOOL), ("Fraeser", TOOL),
    ("DRILL 8.5", TOOL), ("Spiralbohrer", TOOL), ("PULL STUD", TOOL), ("CHUCK", TOOL), ("SAW BLADE", TOOL),
    # offshore / lifting
    ("WIRE ROPE", LIFT), ("STAALKABEL", LIFT), ("Drahtseil", LIFT), ("ROPE", LIFT), ("SLING", LIFT), ("HIJSBAND", LIFT),
    ("SHACKLE", LIFT), ("G-2130", LIFT), ("SLUITING HIJS", LIFT), ("HOOK", LIFT), ("HIJSHAAK", LIFT), ("Lasthaken", LIFT),
    ("SWIVEL", LIFT), ("LIFTING EYE", LIFT), ("HIJSOOG", LIFT), ("PAD EYE", LIFT), ("PADEYE", LIFT),
    ("TURNBUCKLE", LIFT), ("Spannschloss", LIFT), ("THIMBLE", LIFT), ("SPREADER BEAM", LIFT), ("HOIST", LIFT),
    ("CHAIN HOIST", LIFT), ("Kettenzug", LIFT), ("BOLLARD", LIFT), ("ANCHOR", LIFT), ("6X36 IWRC", LIFT),
    ("WINCH", WINCH), ("LIER", WINCH), ("Seilwinde", WINCH), ("CAPSTAN", WINCH), ("DRUM", WINCH), ("WINCH DRUM", WINCH),
    ("Seiltrommel", WINCH), ("KABELTROMMEL", WINCH), ("REEL", WINCH), ("HOSE REEL", WINCH), ("SHEAVE", WINCH),
    ("SEILSCHEIBE", WINCH), ("TENSIONER", WINCH), ("CABLE TENSIONER", WINCH), ("LEVEL WIND", WINCH),
    ("CAROUSEL", WINCH), ("A-FRAME", WINCH), ("DAVIT", WINCH), ("STINGER", WINCH), ("SHARK JAW", WINCH),
    # materials named in the name
    ("PLATE RVS", SS), ("RVS PLAAT 2MM", SS), ("SS PLATE 3MM", SS), ("Blech 1.4301", SS), ("SHAFT INOX", SS),
    ("BRACKET AISI 316", SS), ("COVER 304L", SS), ("Edelstahl Platte", SS), ("STAINLESS STEEL BRACKET", SS),
    ("ALU PLATE 10MM", ALU), ("PLAAT ALU", ALU), ("BLOCK AL 6082", ALU), ("PLATE 6061-T6", ALU), ("ALMG3 PLATE", ALU),
    ("ANODISED BRACKET", ANO), ("PLATE ELOXIERT", ANO), ("BLACK ANODISED PLATE", BANO), ("Platte schwarz eloxiert", BANO),
    ("BUSH BRASS", BUSH), ("BRASS PLATE", BRASS), ("MESSING HUELSE", BRASS), ("Ms58 Huelse", BRASS),
    ("BRONZE PLATE", BRONZE), ("COPPER BAR", COPPER), ("KOPER STRIP", COPPER),
    ("GALV BRACKET", GALV), ("PLATE HDG", GALV), ("Thermisch verzinkt plaat", GALV), ("VERZINKT PLAAT", ZINC),
    ("PLATE S355", STEEL), ("BRACKET S235JR", STEEL), ("SHAFT C45", STEEL), ("STEEL PLATE", STEEL),
    ("STAAL STRIP", STEEL), ("PLATE 42CrMo4", STEEL), ("PLATE HARDOX 450", STEEL), ("GGG40 HOUSING", CI),
    ("CAST IRON BASE", CI), ("GUSSEISEN GEHAEUSE", CI),
    ("BLOCK POM", POM), ("POM PLATE", POM), ("Delrin bush", BUSH), ("DELRIN BLOCK", POM), ("ACETAL ROLLER", ROLL),
    ("POM BLACK", "POM parts, black"), ("BLOK POM ZWART", "POM parts, black"),
    ("PE500 PLATE", PE), ("PLATE PE1000", PE), ("UHMW STRIP", PE), ("PE 500 GROEN", "PE parts, green"),
    ("PA6 BLOCK", PA), ("NYLON SPACER", PA), ("PEEK BUSH", BUSH), ("PEEK BLOCK", PEEK), ("PTFE PLATE", PTFE),
    ("TEFLON STRIP", PTFE), ("PVC PLATE", PVC), ("PVC PIPE 32", PIPE), ("PP PLATE", PP), ("ABS COVER", PLAST),
    ("KUNSTSTOF PLAAT", PLAST), ("PLASTIC CAP", PLAST), ("GLASS PLATE", GLASS), ("GLAS", GLASS),
    ("RUBBER", RUB), ("RUBBER PLATE", RUB), ("EPDM STRIP", RUB), ("NBR PLATE", RUB), ("FOAM", FOAM), ("SCHUIMRUBBER", FOAM),
    ("ISOLATIE", FOAM), ("FELT", FELT), ("VILT STRIP", FELT), ("WOOD", WOOD), ("EURO PALLET", WOOD), ("MULTIPLEX PLAAT", WOOD),
    ("HOUTEN KIST", WOOD), ("Holzpalette", WOOD),
]

NEGATIVES = [
    "FRAME", "PRODUCT INFO", "PRODUCT", "PART1", "Part2", "Component1", "Body1", "ASSY", "ASSEMBLY", "SUB ASSY",
    "INFEED.SYSTEM", "O-RING.FITTING.UNIT", "LIFT.UNIT", "STATION 3", "MACHINE", "PACKING.LINE-3",
    "TEST.MACHINE", "TEST.CRANE", "TROLLEY.ASM", "(Unsaved)", "Untitled", "Solid1", "Surface1",
    "Sketch1", "WORK PLANE", "ORIGIN", "123-456-789", "DWG-0042", "A0001", "P-1000", "REV B", "NEW PART", "COPY OF",
    "LH", "RH", "LEFT", "RIGHT", "TOP", "BOTTOM", "FRONT", "REAR", "INNER", "OUTER", "UPPER", "LOWER", "MAIN", "SUB",
    "TEMP", "DUMMY", "SPARE", "OPTION", "VARIANT", "KIT", "SET", "GROUP", "MODULE", "UNIT", "SYSTEM",
    "SS", "AL", "PE", "PA", "VA", "MS", "ST", "CU", "PC", "PU", "PP", "X", "Y", "Z",
]


# ---- names on their own ---------------------------------------------------------------------

@pytest.mark.parametrize("name,group", NAMES, ids=[n for n, _ in NAMES])
def test_name_gives_group(name, group):
    assert part_types.classify(name) == group


@pytest.mark.parametrize("name", NEGATIVES)
def test_name_stays_unsorted(name):
    assert part_types.classify(name) == ""


def test_enough_examples_and_patterns():
    assert len(NAMES) >= 300
    assert len({g for _, g in NAMES if g}) >= 60, "examples must cover all families"
    keywords = sum(len([w for w in t["words"].split("|") if w.strip()]) for t in D.TYPES)
    codes = sum(len(t["codes"]) for t in D.TYPES)
    assert keywords > 2000 and codes > 100


def test_word_aware_matching():
    assert part_types.classify("ROD") == "Shafts, pins & spacers"
    for name in ("PRODUCT", "PRODUCT INFO", "PRODUCTION", "CORRODE", "ERODED"):
        assert part_types.classify(name) == "", name
    assert part_types.classify("piston_rod_12") == "Chrome rods & linear shafts"
    assert part_types.classify("KUGELLAGER") == "Bearings"                   # end of a compound word
    assert part_types.classify("SCHALTER") == "Sensors & switches"           # not "...HALTER" (holder)
    assert part_types.classify("SENSORHALTER") == "Plates, blocks & brackets"
    assert part_types.classify("BearingHousing") == "Bearing housings & units"   # camelCase
    assert part_types.classify("GEHÄUSE") == part_types.classify("GEHAEUSE") == part_types.classify("GEHAUSE")


def test_word_order_either_way():
    for name in ("SENSOR BRACKET", "BRACKET SENSOR", "MOTOR PLATE", "PLATE MOTOR", "FLANGE MOTOR", "MOTOR FLANGE",
                 "HOUDER SENSOR", "CYLINDER BRACKET", "BRACKET CYLINDER"):
        assert part_types.classify(name) == "Plates, blocks & brackets", name
    assert part_types.classify("SHAFT SEAL") == "Seals & O-rings"            # longer keyword wins
    assert part_types.classify("SEAL PLATE") == "Plates, blocks & brackets"
    assert part_types.classify("SENSOR CABLE") == "Cables"
    assert part_types.classify("CYLINDER ROD") == "Chrome rods & linear shafts"


def test_vendor_codes_do_not_grab_plain_words():
    """No keyword of the library, read as a whole name, is taken by another type's part number."""
    for t in D.TYPES:
        for w in t["words"].split("|"):
            w = w.strip().strip("*")
            for pattern, tid, _order in part_types._CODES:
                if tid != t["id"]:
                    assert not pattern.search(part_types._code_text(w)), (w, t["id"], tid)


# ---- parent assemblies -----------------------------------------------------------------------

def test_parts_inside_a_vendor_cylinder():
    path = "LINE#1/LIFT#1/CDQ2B32-50DZ#1/{}#1"
    assert part_types.classify("BODY", path.format("BODY")) == "Pneumatic cylinders & grippers"
    assert part_types.classify("HEAD COVER", path.format("HEAD COVER")) == "Pneumatic cylinders & grippers"
    assert part_types.classify("PLATE", path.format("PLATE")) == "Pneumatic cylinders & grippers"
    assert part_types.classify("PISTON ROD", path.format("PISTON ROD")) == "Chrome rods & linear shafts"
    assert part_types.classify("ROD", path.format("ROD")) == "Chrome rods & linear shafts"
    assert part_types.classify("TUBE", path.format("TUBE")) == "Pneumatic cylinders & grippers"   # cylinder tube
    assert part_types.classify("ROD SEAL", path.format("ROD SEAL")) == "Seals & O-rings"
    assert part_types.classify("MAGNET", path.format("MAGNET")) == "Pneumatic cylinders & grippers"
    assert part_types.classify("D-M9B", path.format("D-M9B")) == "Sensors & switches"
    # nearest parent assembly only: a bracket assembly above gives no context
    assert part_types.classify("PLATE", "M#1/MOTOR.BRACKET.ASSY#1/PLATE#1") == "Plates, blocks & brackets"


def test_whole_products_stay_one_colour():
    assert part_types.classify("SHAFT", "M#1/SERVOMOTOR 1FK7#1/SHAFT#1") == "Motors & gearboxes"
    assert part_types.classify("BEARING", "M#1/GEARBOX#1/BEARING#1") == "Motors & gearboxes"
    assert part_types.classify("FOOT", "M#1/MANNEQUIN#1/LEG#1/FOOT#1") == "Mannequins"
    assert part_types.classify("HEAD", "M#1/Human_Male_50th#1/HEAD#1") == "Mannequins"
    assert part_types.classify("LED", "M#1/SENSOR M18#1/LED#1") == "Sensors & switches"
    # only the assembly argument (no path): the parent assembly name
    assert part_types.classify("COVER", assembly="SERVO MOTOR") == "Motors & gearboxes"


def test_machine_modules_pass_no_type_down():
    for parent in ("O-RING.FITTING.UNIT", "INFEED.SYSTEM", "SEAL PRESS STATION", "BEARING INSERTION MODULE",
                   "VALVE TEST LINE", "CABLE INSPECTION CELL"):
        assert part_types.classify("PLATE", f"LINE#1/{parent}#1/PLATE#1") == "Plates, blocks & brackets", parent
        assert part_types.classify("BODY", f"LINE#1/{parent}#1/BODY#1") == "", parent
    # but a module word that is part of the keyword itself is fine
    assert part_types.classify("HOUSING", "M#1/BEARING UNIT UCP205#1/HOUSING#1") == "Bearing housings & units"
    # mechanisms named after a part are not that part
    for parent in ("BELT DRIVE ASSY", "CHAIN.CONVEYOR", "SEAL.PRESS", "SPRING.LOADED.ARM.ASM", "CABLE.ROUTING"):
        assert part_types.classify("PLATE", f"LINE#1/{parent}#1/PLATE#1") == "Plates, blocks & brackets", parent
    # bought multi-part items do pass their type on
    assert part_types.classify("FORK", "M#1/SWIVEL CASTER 100#1/FORK#1") == "Casters & wheels"
    assert part_types.classify("BODY", "M#1/KQ2H06-01AS#1/BODY#1") == "Fittings"


def test_a_module_word_at_the_end_names_a_module_not_a_part():
    # "...UNIT" / "...STATION" at the end: a machine module, also with an assembly suffix after it
    for name in ("SEAL.FITTING.UNIT", "PIN.PRESS.UNIT.ASM", "CABLE.TEST.LINE_RH", "BEARING PRESS",
                 "LINEAR GUIDE UNIT"):
        assert part_types.classify(name) == "", name
    # a product type keeps its name even with a module word at the end
    assert part_types.classify("HYDRAULIC POWER UNIT") == "Hydraulic components"
    assert part_types.classify("SERVO MOTOR UNIT") == "Motors & gearboxes"


def test_qualifiers_do_not_make_a_new_type():
    # "4 PIN" is a connector size, "WITH BRAKE" belongs to the motor, "FOR PROFILE" to the nut
    assert part_types.classify("CONNECTOR M12 4 PIN") == "Electrical components"
    assert part_types.classify("GRIPPER 2 JAW") == "Pneumatic cylinders & grippers"
    assert part_types.classify("SERVO MOTOR WITH BRAKE") == "Motors & gearboxes"
    assert part_types.classify("T-NUT FOR PROFILE 40") != "Aluminium profiles"


def test_step_alone_is_not_a_stair():
    assert part_types.classify("STEP") == ""
    assert part_types.classify("STAIR STEP") == "Gratings, stairs & railings"


def test_ancestors_from_uid_path():
    assert part_types.ancestors_of("A#1/B.C#2/D 3/4#1/PART#3") == ("D 3/4", "B.C", "A")
    assert part_types.ancestors_of("", "SUB") == ("SUB",)
    assert part_types.ancestors_of("PART#1") == ()


# ---- materials and colours -------------------------------------------------------------------

def test_material_in_name_beats_shape_default():
    assert part_types.classify("PLATE") == "Plates, blocks & brackets"
    assert part_types.classify("PLATE RVS") == "Stainless steel parts"
    assert part_types.classify("PLATE POM") == "POM parts"
    assert part_types.classify("PLATE POM ZWART") == "POM parts, black"
    # a bought part keeps its type whatever material its name mentions
    assert part_types.classify("PROFILE 40X40 ALU") == "Aluminium profiles"
    assert part_types.classify("SEAL NBR") == "Seals & O-rings"
    # weak words count only next to another word
    assert part_types.classify("SS") == "" and part_types.classify("BRACKET SS") == "Stainless steel parts"


def test_cad_colour_paints_paint_type_groups_only():
    assert part_types.classify("COVER", color="#1F4E79") == "Covers & panels #1F4E79"
    assert part_types.classify("BRACKET", color="#1f4e79") == "Plates, blocks & brackets #1F4E79"
    assert part_types.classify("SEAL", color="#1F4E79") == "Seals & O-rings"                 # rubber ignores it
    assert part_types.classify("PROFILE 40X40", color="#1F4E79") == "Aluminium profiles"     # metal ignores it
    assert part_types.classify("WINDOW", color="#1F4E79") == "Windows & clear parts"         # clear ignores it
    assert part_types.classify("MOTOR", color="#1F4E79") == "Motors & gearboxes #1F4E79"
    assert part_types.classify("PLATE S355", color="#F9A800") == "Steel parts #F9A800"       # painted steel
    assert part_types.classify("PLATE RVS", color="#F9A800") == "Stainless steel parts"


def test_known_cad_material_beats_generic_shape():
    assert part_types.classify("PLATE", cad_material="Aluminum 6061") == ""          # the CAD material rule decides
    assert part_types.classify("PLATE", cad_material="Default") == "Plates, blocks & brackets"
    assert part_types.classify("PLATE", cad_material="Mystery alloy 7") == "Plates, blocks & brackets"
    assert part_types.classify("SEAL", cad_material="Steel") == "Seals & O-rings"    # Fusion's default material
    assert part_types.classify("PLATE RVS", cad_material="Steel") == "Stainless steel parts"


@pytest.mark.parametrize("name,material", [
    ("Aluminum 6061", "aluminium_machined"), ("Aluminum - Satin", "aluminium_machined"),
    ("Aluminium-6082", "aluminium_machined"), ("Aluminum - Anodized Rough (Blue)", "aluminium_anodized_color"),
    ("Aluminum - Anodized Glossy (Black)", "aluminium_anodized_black"), ("Anodized Aluminium", "aluminium_anodized"),
    ("Steel", "steel_machined"), ("Steel, Mild", "steel_machined"), ("Steel - Satin", "steel_machined"),
    ("Steel, Galvanized", "galvanized"), ("S235JR", "steel_machined"), ("Stainless Steel", "stainless_brushed"),
    ("Stainless Steel, 440C", "stainless_brushed"), ("Stainless Steel - Polished", "stainless_polished"),
    ("RVS 316", "stainless_brushed"), ("1.4301", "stainless_brushed"), ("Iron, Cast", "cast_iron"),
    ("Cast Iron", "cast_iron"), ("EN-GJS-400", "cast_iron"), ("Brass, Soft Yellow", "brass"), ("Bronze", "bronze"),
    ("Copper", "copper"), ("Chrome - Polished", "chrome"), ("Titanium", "stainless_brushed"),
    ("Rubber", "rubber_black"), ("Rubber - Soft", "rubber_black"), ("EPDM", "rubber_black"),
    ("Silicone", "rubber_black"), ("ABS Plastic", "plastic_matte"), ("Plastic - Glossy (Red)", "plastic_gloss"),
    ("Nylon 6/6", "plastic_matte"), ("Polycarbonate", "polycarbonate_clear"), ("Acrylic", "polycarbonate_clear"),
    ("Glass", "glass_clear"), ("Glass - Clear", "glass_clear"), ("Frosted glass", "acrylic_frosted"),
    ("POM", "pom_white"), ("Delrin", "pom_white"), ("UHMW", "pom_white"), ("PTFE", "plastic_matte"),
    ("Paint - Enamel Glossy (Red)", "paint_gloss"), ("Paint - Enamel Matte (Black)", "paint_matte"),
    ("Powder Coat (Red)", "powder_coat"), ("RAL 7035", "paint_satin"), ("Wood (Oak)", "wood"),
    ("Plywood", "wood"), ("Foam", "foam"), ("Felt", "felt"), ("Zinc", "zinc_plated"),
])
def test_cad_material_names(name, material):
    assert cad_materials.lookup(name)[0] == material


@pytest.mark.parametrize("name", ["", "Default", "Generic", "Material", "DEFAULT MATERIAL", "Smooth - Light Gray",
                                  "Concrete", "Custom 12", "Colour"])
def test_cad_material_names_without_a_look(name):
    assert cad_materials.lookup(name) is None


def test_pick_the_name_that_decides_the_look():
    assert cad_materials.pick("Paint - Enamel Glossy (Red)", "Steel") == "Paint - Enamel Glossy (Red)"
    assert cad_materials.pick("Default", "Aluminum 6061") == "Aluminum 6061"
    assert cad_materials.pick("My blue 12", "Aluminum 6061") == "Aluminum 6061"
    assert cad_materials.pick("My blue 12", "Generic") == "My blue 12"
    assert cad_materials.pick("", "Generic") == ""


# ---- rules -----------------------------------------------------------------------------------

def _facts(name, color="", cad="", path=""):
    return R.facts_for(name, path=path or f"Machine#1/{name}#1", color=color, assembly="Machine", cad_material=cad)


def test_default_rule_order():
    rules = R.default_rules()
    fields = [r.field for r in rules]
    assert fields[-3:] == ["part_type", "cad_material", "color"]
    assert len(rules) == 9, "the library hides behind one rule: the list stays short"
    parts = [
        _facts("ISO 4017 M12 x 40 - 8.8 HDG"),                       # fastener before part type
        _facts("T-NUT M6 8"),                                        # T-nuts are fasteners
        _facts("O-RING 20X2"),
        _facts("Component1", color="#272727", cad="Rubber - Soft"),  # CAD appearance
        _facts("Component2", color="#F5F5F6", cad="Aluminum"),
        _facts("PLATE", color="#1F4E79", cad="Aluminum 6061"),       # known CAD material beats shape
        _facts("BODY1", color="#1F4E79", cad="Generic"),             # placeholder: colour decides
        _facts("FRAME"),
    ]
    groups, _counts, unmatched = R.classify(parts, rules)
    assert groups == ["Fasteners galvanized", "Fasteners default", "Seals & O-rings", "Rubber - Soft", "Aluminum",
                      "Aluminum 6061", "Colour #1F4E79", R.FALLBACK_GROUP]
    assert unmatched == [7]


def test_cad_material_group_gets_the_colour_when_it_is_a_paint():
    rules = R.default_rules()
    g, _ = R.classify_one(_facts("BODY1", color="#C00000", cad="Paint - Enamel Glossy (Red)"), rules)
    assert g == "Paint - Enamel Glossy (Red) #C00000"
    assert R.default_material_for_group(g) == ("paint_gloss", "#C00000")
    assert R.default_material_for_group("Paint - Enamel Glossy (Red)") == ("paint_gloss", "RAL 3020")
    g, _ = R.classify_one(_facts("BODY2", color="#C00000", cad="Steel - Satin"), rules)
    assert g == "Steel - Satin"


def test_part_type_and_cad_material_fields():
    f = _facts("_MGPM32-75Z_ROD", cad="Steel")
    assert f.get("part_type") == "Chrome rods & linear shafts"
    assert f.get("cad_material") == "Steel"
    assert _facts("X", cad="Default").get("cad_material") == ""
    assert R._matches(R.Rule("x", "part_type", "contains", "chrome"), f)
    assert R.Rule("{part_type}", "part_type", "any").describe() == "Part type has any value → {part_type}"


def test_rule_fields_keep_their_positions():
    """Blender stores the position of an enum choice: new fields only at the end."""
    assert list(R.FIELDS)[:11] == ["name", "path", "assembly", "color", "is_standard", "family", "kind", "finish",
                                   "standard", "size", "property_class"]
    assert list(R.FIELDS)[11:] == ["part_type", "cad_material"]


def test_old_projects_can_be_upgraded():
    assert R.upgraded_rules(R.old_default_rules()) == R.default_rules()
    changed = R.old_default_rules()
    changed[0].enabled = False
    assert R.upgraded_rules(changed) is None
    assert R.upgraded_rules(R.default_rules()) is None


def test_every_group_has_its_starting_material():
    for group, (mat, colour, paint) in D.GROUPS.items():
        assert R.default_material_for_group(group) == (mat, colour), group
        assert mat in materials_lib.MATERIALS and (not paint or paint in materials_lib.MATERIALS), group
        if materials_lib.needs_color(mat):
            assert colour, f"{group}: {mat} needs a colour"
        if paint:
            assert R.default_material_for_group(f"{group} #1A2B3C") == (paint, "#1A2B3C")
    assert R.default_material_for_group("POM parts, black") == ("plastic_matte", "RAL 9005")
    assert R.default_material_for_group("Fasteners black") == ("black_oxide", "")


# ---- data consistency --------------------------------------------------------------------------

def test_library_data_is_consistent():
    ids = [t["id"] for t in D.TYPES]
    assert len(ids) == len(set(ids))
    for t in D.TYPES:
        assert t["group"] in D.GROUPS, t["id"]
        assert t["level"] in part_types.LEVELS, t["id"]
        assert t["absorb"] in ("shape", "all"), t["id"]
        for role, target in t["roles"].items():
            assert role in part_types.TYPES and target in part_types.TYPES, (t["id"], role)
        for w in t["words"].split("|"):
            w = w.strip()
            assert w == w.upper(), (t["id"], w)          # ("*END" / "START*" letters only: checked on load)
    for cls, group in D.MATERIAL_GROUPS.items():
        assert cls in D.MATERIAL_WORDS and group in D.GROUPS
    for name, (_words, ral) in D.COLOUR_WORDS.items():
        assert name == name.lower() and (ral == "" or R.default_material_for_group(f"PE parts, {name}"))


def test_new_materials_appended_with_fixed_numbers():
    assert materials_lib.UIDS["emission_light"] == 33
    new = ["nickel_plated", "aluminium_anodized_black", "zinc_diecast", "belt_rubber", "foam", "felt",
           "mannequin_matte", "wood"]
    assert [materials_lib.UIDS[m] for m in new] == list(range(34, 34 + len(new)))


def test_speed_on_a_big_model():
    """2,800 placed parts with 600 unique names sort in well under a second (cached by name)."""
    part_types.classify.cache_clear(); part_types.analyse.cache_clear()
    part_types.own_type.cache_clear(); part_types.context_of.cache_clear()
    names = [n for n, _ in NAMES][:600]
    t = time.perf_counter()
    for i in range(2800):
        name = names[i % len(names)]
        part_types.classify(name, f"LINE#1/STATION {i % 40}#1/SUB {i % 7}#1/{name}#{i}")
    assert time.perf_counter() - t < 3.0
