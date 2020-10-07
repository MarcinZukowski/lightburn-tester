#!/usr/bin/env python3

import optparse
import re
import shlex
import sys


DEFAULT_FILENAME = "test.lbrn"
PROLOGUE_FILENAME = "data/prologue.xml"
EPILOGUE_FILENAME = "data/epilogue.xml"
DEFAULT_LEFT_MARGIN = 950
DEFAULT_MODE = "Fill"
FONT_SIZE_TITLE = 8
FONT_SIZE_LABELS = 7
FONT_SIZE_VALUES = 5
FONT_SIZE_TILES = 4
BOX_SIZE = 14
BOX_SPACE = 20
BOX_SIZE_HALF = BOX_SIZE / 2
DEFAULT_TEXT_ON_TILES = False

KEY_SQUARE = "square"
KEY_CIRCLE = "circle"
KEY_MUFFIN = "muffin"
KEY_TEXT = "text"
DEFAULT_SHAPE = KEY_MUFFIN
shapes = [KEY_MUFFIN, KEY_SQUARE, KEY_CIRCLE, KEY_TEXT]
shape = DEFAULT_SHAPE

text_on_tiles = DEFAULT_TEXT_ON_TILES

KEY_DEFAULT = "default"
KEY_SHORT = "short"

first_line = True

# Available cut modes
modes = {
    "Fill": "Scan",
    "Fill+Line": "Scan+Cut",
    "Line": "Cut",
    "Scan": "Scan",
    "Cut": "Cut",
    "Scan+Cut": "Scan+Cut",
}


# Helper class to keep one setting information
class Setting:
    def __init__(self, name, default, short=None):
        self.name = name
        self.default= default
        self.short = short or name

KW_POWERSCALE = "powerScale"

# Available settings
settings_list = [
    Setting("power", 80, "p"),
    Setting("speed", 100, "s"),
    Setting("interval", 0.1, "i"),
    Setting("numPasses", 1, "np"),
    Setting("angle", 0, "a"),
    Setting("frequency", None, "f"),
    Setting(KW_POWERSCALE, 100, "ps"),
]

settings_map = {v.name: v for v in settings_list}

# Generated cut values
cut = {
    "index": 0,
    "name": "FOO",
    "minPower": 20,
    "maxPower": 20,
    "minPower2": 20,
    "maxPower2": 20,
    "speed": 100,
    "kerf": 0,
    "zOffset": 0,
    "enableLaser1": 1,
    "enableLaser2": 0,
    "startDelay": 0,
    "endDelay": 0,
    "throughPower": 0,
    "throughPower2": 0,
    "enableCutThroughStart": 0,
    "enableCutThroughEnd": 0,
    "priority": 1,
    "frequency": 20000,
    "overrideFrequency": 0,
    "PPI": 200,
    "enablePPI": 0,
    "doOutput": 1,
    "hide": 0,
    "runBlower": 1,
    "autoBlower": 0,
    "blowerSpeedOverride": 0,
    "blowerSpeedPercent": 100,
    "overcut": 0,
    "rampLength": 0,
    "rampOuter": 0,
    "numPasses": 1,
    "zPerPass": 0,
    "perforate": 0,
    "perfLen": 0.1,
    "perfSkip": 0.1,
    "dotMode": 0,
    "dotTime": 1,
    "dotSpacing": 0.1,
    "manualTabs": 1,
    "tabSize": 0.5,
    "tabCount": 1,
    "tabSpacing": 50,
    "skipInnerTabs": 0,
    "tabsUseSpacing": 1,
    "scanOpt": "mergeAll",
    "bidir": 1,
    "crossHatch": 0,
    "overscan": 0,
    "overscanPercent": 2.5,
    "floodFill": 0,
    "interval": 0.1,
    "angle": 0,
    "cellsPerInch": 50,
    "halftoneAngle": 22.5,
}

current_y = 0
body = ""
lmargin = DEFAULT_LEFT_MARGIN
parser = None
mode = None

current_cut = 0
cut_map = {}


class MyParser(optparse.OptionParser):
    def format_epilog(self, formatter):
        res = "\nAvailable setting names: "
        for s in settings_list:
            res += "\n  {0:10s} default: {1}".format(s.name, s.default)
        res += """

Each setting is specified as <name>=<values1>,<values2>

Each "values" can be one of:
* constant value, e.g. "20" or "3.5")
* range of values with step: "min-max@step", e.g. "0-100@25" will generate 0,25,50,75,100 
"""
        return res


def error(msg):
    print("\nERROR: {0}".format(msg))
    sys.exit(1)


def usage(msg):
    global parser
    parser.print_help()
    error(msg)


def isfloat(value):
    try:
        float(value)
        return True
    except ValueError:
        return False


def fmt(v):
    return f"{v:.3f}".rstrip("0").rstrip(".")


# Helper to handle special "power" behavior
def set_cut(k, v):
    if k == "power":
        set_cut("minPower", v)
        set_cut("maxPower", v)
    elif k == "numPasses":
        cut[k] = int(v)
    elif k == "frequency":
        cut[k] = int(v)
        cut["overrideFrequency"] = 1
    else:
        cut[k] = v


def gen_dynamic(parents, current, next):
    global body, current_y, current_cut, cut, mode, lmargin, first_line
    (name, values) = current
    if len(next) > 0:
        for v in values:
            set_cut(name, v)
            new_parents = parents + [(name, v)]
            gen_dynamic(new_parents, next[0], next[1:])
    else:
        if first_line:

            if len(parents) > 0:
                parents_header = ", ".join([k for (k, v) in parents])
                add_text(lmargin - len(values) * BOX_SPACE, current_y, FONT_SIZE_LABELS, parents_header)

            current_y += 2 + add_text(lmargin - (len(values) * BOX_SPACE) / 2, current_y,
                                      FONT_SIZE_LABELS, name, ah=1)

            x = lmargin
            for v in values:
                add_text(x - BOX_SIZE_HALF, current_y, FONT_SIZE_VALUES, fmt(v), ah=1)
                x -= BOX_SPACE

            current_y += 4 + FONT_SIZE_VALUES

            first_line = False

        x = lmargin

        header = ""
        if len(parents) > 0:
            header = ",  ".join([f"{settings_map[k].short}={fmt(v)}" for (k, v) in parents])

        for v in values:
            new_parents = parents + [(name, v)]
            new_parents = filter(lambda x: x[0] != KW_POWERSCALE, new_parents)
            cut_name = ",".join([f"{k}={fmt(v)}" for (k, v) in new_parents])

            cut_index = cut_map.get(cut_name)

            set_cut(name, v)

            if not cut_index:
                # Create a new cut
                current_cut += 1

                set_cut("index", current_cut)
                set_cut("name", cut_name)

                cut_items = filter(lambda x: x[0] != KW_POWERSCALE, cut.items())
                cut_values = "".join([f"""<{k} Value="{v}"/>\n""" for (k, v) in cut_items])
                body += f"""
<CutSetting type="{mode}">
{cut_values}
</CutSetting>
"""
                cut_map[cut_name] = current_cut
                cut_index = current_cut

            shape_meta = f'''CutIndex="{cut_index}"'''
            power_scale = cut.get(KW_POWERSCALE)
            if power_scale is not None:
                shape_meta += f''' PowerScale="{power_scale}"'''

            # Create a new shape
            cx = x - BOX_SIZE_HALF
            cy = current_y + BOX_SIZE_HALF

            if shape == KEY_SQUARE:
                body += f"""
<Shape Type="Rect" {shape_meta} W="{BOX_SIZE}" H="{BOX_SIZE}" Cr="0">
    <XForm>1 0 0 1 {cx} {cy}</XForm>
</Shape>
"""
            elif shape == KEY_CIRCLE:
                body += f"""
<Shape Type="Ellipse" {shape_meta} Rx="{BOX_SIZE_HALF}" Ry="{BOX_SIZE_HALF}">
    <XForm>1 0 0 1 {cx} {cy}</XForm>
</Shape>
"""
            elif shape == KEY_MUFFIN:
                scale = BOX_SIZE / 20 * 1.2
                def sx(v):
                    return cx + scale * v

                def sy(v):
                    return cy + scale * v

                body += f"""
<Shape Type="Path" {shape_meta}>
    <XForm>1 0 0 1 0 0</XForm>
    <V vx="{sx(1.5195313)}" vy="{sy(-8.0429688)}" c0x="{sx(6.8419399)}" c0y="{sy(-7.7834616)}" c1x="{sx(1.1787055)}" c1y="{sy(-8.0638018)}"/>
    <V vx="{sx(11)}" vy="{sy(1.9453125)}" c0x="1" c0y="0" c1x="{sx(11.018312)}" c1y="{sy(-3.3833861)}"/>
    <V vx="{sx(6.0117188)}" vy="{sy(10.058594)}" c0x="1" c0y="0" c1x="1" c1y="0"/>
    <V vx="{sx(-3.9960938)}" vy="{sy(10.058594)}" c0x="1" c0y="0" c1x="1" c1y="0"/>
    <V vx="{sx(-9)}" vy="{sy(1.9453125)}" c0x="{sx(-9.0065451)}" c0y="{sy(-3.384521)}" c1x="1" c1y="0"/>
    <V vx="{sx(0.49609375)}" vy="{sy(-8.0429688)}" c0x="{sx(0.83691972)}" c0y="{sy(-8.0638018)}" c1x="{sx(-4.8272738)}" c1y="{sy(-7.7804079)}"/>
    <P T="B" p0="0" p1="1"/>
    <P T="L" p0="1" p1="2"/>
    <P T="L" p0="2" p1="3"/>
    <P T="L" p0="3" p1="4"/>
o    <P T="B" p0="4" p1="5"/>
    <P T="B" p0="5" p1="0"/>
</Shape>
"""
            elif shape == KEY_TEXT:
                body += f"""
<Shape Type="Text" CutIndex="{current_cut}" Font="Arial,-1,100,5,50,0,0,0,0,0" 
     Str="ABC" H="8" LS="0" LnS="0" Ah="1" Av="1" Weld="1">
        <XForm>1 0 0 1 {cx} {cy-4}</XForm>
</Shape>            
<Shape Type="Text" CutIndex="{current_cut}" Font="Arial,-1,100,5,50,0,0,0,0,0" 
     Str="xyz!" H="8" LS="0" LnS="0" Ah="1" Av="1" Weld="1">
        <XForm>1 0 0 1 {cx} {cy+4}</XForm>
</Shape>            
"""
            else:
                error(f"Shape not implemented: {shape}")

            if text_on_tiles:
                label = f"{settings_map[name].short}={fmt(v)}"
                if header:
                    fs = FONT_SIZE_TILES
                    add_text(x - BOX_SIZE_HALF, current_y + BOX_SIZE_HALF, fs, header, ah=1, av=2)
                add_text(x - BOX_SIZE_HALF, current_y + BOX_SIZE_HALF + fs, fs, label, ah=1, av=2)

            x -= BOX_SPACE

        if header:
            add_text(x, current_y + BOX_SIZE_HALF, FONT_SIZE_VALUES, header, av=1)

        current_y += BOX_SPACE


def add_text(x, y, h, s, ah=0, av=0):
    global body
    body += f"""
<Shape Type="Text" CutIndex="0" Font="Arial,-1,100,5,50,0,0,0,0,0" 
     Str="{s}" H="{h}" LS="0" LnS="0" Ah="{ah}" Av="{av}" Weld="1">
        <XForm>1 0 0 1 {x} {y}</XForm>
</Shape>            
"""
    return h


def main():
    global current_y, mode, parser, body, text_on_tiles, shape

    parser = MyParser(usage='Usage: %prog [settings] ',
                      description="Generate ")
    parser.add_option("-f", "--filename", help="File name to generate")
    parser.add_option("-m", "--mode", help=f"Mode (values: {','.join(modes.keys())})")
    parser.add_option("-t", "--text", help="Text on tiles", action = "store_true")
    parser.add_option("-s", "--shape", help=f"Mode (values: {','.join(shapes)})")

    (options, args) = parser.parse_args()
    filename = options.filename or DEFAULT_FILENAME
    mode = options.mode or DEFAULT_MODE
    assert mode in modes, f"Unknown mode: {mode}, allowed values: {', '.join(modes.keys())}"
    mode = modes[mode]
    text_on_tiles = options.text or DEFAULT_TEXT_ON_TILES

    shape = options.shape or DEFAULT_SHAPE
    assert shape in shapes, f"Unknown shape: {shape}"

    if len(args) == 0:
        usage("Need to provide some settings")

    seen = []
    constants = []
    dynamic = []
    mul = 1

    for arg in args:
        sp = arg.split("=")
        assert len(sp) == 2, f"wrong setting format: '{arg}'"

        name = sp[0]
        assert name in settings_map, f"unknown setting: '{name}'"
        assert name not in seen, f"repeated setting: '{name}'"
        seen.append(name)

        values_list = sp[1].split(",")
        genvalues = []
        for values in values_list:
            if isfloat(values):
                genvalues.append(float(values))
                continue
            m = re.match(r"(\d+(?:\.\d+|))-(\d+(?:\.\d+|))@(\d+(?:\.\d+|))", values)
            assert m, f"wrong values format: '{values}'"
            start = float(m.group(1))
            end = float(m.group(2))
            step = float(m.group(3))
            while start <= end:
                genvalues.append(start)
                start += step
        res = (name, genvalues)
        if len(genvalues) == 1:
            constants.append(res)
        else:
            dynamic.append(res)
            if name != KW_POWERSCALE:
                mul *= len(genvalues)

    if mul > 28:
        error(f"Too many combinations ({mul}), max is 28")

    with open(PROLOGUE_FILENAME, 'r') as file:
        prologue = file.read()
    with open(EPILOGUE_FILENAME, 'r') as file:
        epilogue = file.read()

    current_y += 4 + add_text(lmargin, current_y, FONT_SIZE_TITLE, f"LightBurn Test (mode={mode})")

    for (c, v) in constants:
        val = v[0]
        set_cut(c, val)
    current_y += 2 + add_text(lmargin, current_y, FONT_SIZE_LABELS,
                              ", ".join([f"{c}={fmt(v[0])}" for (c, v) in constants]))

    gen_dynamic([], dynamic[0], dynamic[1:])


    # Add "Generated" note
    cmdline = " ".join(map(shlex.quote, sys.argv))
    body += f"""
    <Notes ShowOnLoad="0" Notes="Generated with lightburn-tester, command:&#10;  {cmdline}"/>
"""

    with open(filename, 'w') as out:
        out.write(prologue)
        out.write(body)
        out.write(epilogue)

    print(f"{filename} generated")


main()
