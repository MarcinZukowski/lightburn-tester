#!/usr/bin/env python3

import optparse
import re
import shlex
import sys


DEFAULT_FILENAME = "test.lbrn"
PROLOGUE_FILENAME = "data/prologue.xml"
EPILOGUE_FILENAME = "data/epilogue.xml"
DEFAULT_LEFT_MARGIN = 1150
DEFAULT_MODE = "Fill"

# Available cut modes
modes = {
    "Fill": "Scan",
    "Fill+Line": "Scan+Cut",
    "Line": "Cut",
    "Scan": "Scan",
    "Cut": "Cut",
    "Scan+Cut": "Scan+Cut",
}

# Available settings
settings = {
    "power": 80,
    "speed": 100,
    "interval": 0.1,
    "passCount": 1,
    "angle": 0,
}

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
current_cut = 1
parser = None
mode = None


class MyParser(optparse.OptionParser):
    def format_epilog(self, formatter):
        res = "\nAvailable setting names: "
        for k, v in settings.items():
            res += "\n  {0:10s} default: {1}".format(k, v)
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


# Helper to handle special "power" behavior
def set_cut(k, v):
    if k == "power":
        set_cut("minPower", v)
        set_cut("maxPower", v)
    else:
        cut[k] = v


def gen_dynamic(parents, current, next):
    global body, current_y, current_cut, cut, mode
    (name, values) = current
    if len(next) > 0:
        for v in values:
            set_cut(name, v)
            new_parents = parents + [(name, v)]
            gen_dynamic(new_parents, next[0], next[1:])
    else:
        if len(parents) > 0:
            header = ", ".join([f"{k}: {v}" for (k, v) in parents])
            add_text(lmargin, current_y, 8, header)
            current_y += 15
            add_text(lmargin, current_y, 8, f"{name}:")

        x = lmargin - 50

        for v in values:
            set_cut("index", current_cut)
            set_cut(name, v)

            new_parents = parents + [(name, v)]
            cutname = ",".join([f"{k}: {v:.2f}" for (k, v) in new_parents])
            set_cut("name", cutname)

            cutvalues = "".join([f"""<{k} Value="{v}"/>\n""" for (k, v) in cut.items()])
            body += f"""
<CutSetting type="{mode}">
{cutvalues}
</CutSetting>
"""

            body += f"""
<Shape Type="Rect" CutIndex="{current_cut}" W="10" H="10" Cr="0">
    <XForm>1 0 0 1 {x-5} {current_y+5}</XForm>
</Shape>
"""
            add_text(x, current_y + 15, 6, f"{v:.2f}")
            x -= 20

            current_cut += 1

        current_y += 30


def add_text(x, y, h, s):
    global body
    body += f"""
<Shape Type="Text" CutIndex="0" Font="Arial,-1,100,5,50,0,0,0,0,0" 
     Str="{s}" H="{h}" LS="0" LnS="0" Ah="0" Av="0" Weld="1">
        <XForm>1 0 0 1 {x} {y}</XForm>
</Shape>            
"""


def main():
    global current_y, mode, parser, body

    parser = MyParser(usage='Usage: %prog [settings] ',
                      description="Generate ")
    parser.add_option("-f", "--filename", help="File name to generate")
    parser.add_option("-m", "--mode", help=f"Mode (values: {','.join(modes.keys())})")

    (options, args) = parser.parse_args()
    filename = options.filename or DEFAULT_FILENAME
    mode = options.mode or DEFAULT_MODE
    assert mode in modes, f"Unknown mode: {mode}"
    mode = modes[mode]

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
        assert name in settings, f"unknown setting: '{name}'"
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
            mul *= len(genvalues)

    if mul > 28:
        error(f"Too many combinations ({mul}), max is 28")

    with open(PROLOGUE_FILENAME, 'r') as file:
        prologue = file.read()
    with open(EPILOGUE_FILENAME, 'r') as file:
        epilogue = file.read()

    add_text(lmargin, current_y, 16, f"LightBurn Test (mode={mode})")
    current_y += 30

    for (c, v) in constants:
        add_text(lmargin, current_y, 10, f"{c}: {v[0]}")
        current_y += 15

    current_y += 10

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
