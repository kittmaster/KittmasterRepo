import xbmc
import sys

def main():
    if not hasattr(sys, 'listitem'):
        xbmc.log('context.preshowexperience: Not launched as a context menu - aborting')
        return
    xbmc.executebuiltin('RunScript(script.preshowexperience,experience)')

if __name__ == '__main__':
    main()