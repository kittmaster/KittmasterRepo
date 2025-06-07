# Author: roidy
# License: MIT

"""
USAGE:

RunScript(special://skin/extras/scripts/SetSlidersToColor.py,{Window id},
                                                             {Alpha control id},
                                                             {Red control id},
                                                             {Green control id},
                                                             {Blue control id},
                                                             {Skin String containing hex color (AARRGGBB)})

RunScript(special://skin/extras/scripts/SetSlidersToColor.py,10000,9001,9002,9003,9004,MyColorString)
"""

if __name__ == '__main__':
    import sys
    import xbmc
    import xbmcgui

    try:
        win = xbmcgui.Window(int(sys.argv[1]))
        alpha_control = win.getControl(int(sys.argv[2]))
        red_control = win.getControl(int(sys.argv[3]))
        green_control = win.getControl(int(sys.argv[4]))
        blue_control = win.getControl(int(sys.argv[5]))
        hex_color = xbmc.getInfoLabel(f"Skin.String({sys.argv[6]})")

        percentages = {c: int(hex_color[i:i+2], 16) / 255 * 100
                    for i, c in zip(range(0, 8, 2), ['AA', 'RR', 'GG', 'BB'])}
        
        alpha_control.setPercent(percentages['AA'])
        red_control.setPercent(percentages['RR'])
        green_control.setPercent(percentages['GG'])
        blue_control.setPercent(percentages['BB'])
    
    except:
        pass