import xbmc

# Check if logging is disabled (skin setting)
logging_enabled = xbmc.getInfoLabel("Skin.HasSetting(disablecounterscriptloggingall)").lower() == 'true'

# Fetch the "seed" (in seconds) from a Kodi skin string for movies:
seed_str = xbmc.getInfoLabel("Skin.String(moviemetascrollingdelayvaluevarb)")
try:
    seed_val = int(seed_str)
except ValueError:
    seed_val = 7  # fallback if user typed something invalid

# Read the current countdown value for movies:
current_str = xbmc.getInfoLabel("Window(Home).Property(ItemListCountDownTimerMovie)")
try:
    current_val = int(current_str)
except ValueError:
    current_val = seed_val

# Decrement or reset the countdown for movies:
if current_val > 0:
    current_val -= 1
else:
    # We hit 0, so do the Move() animation for movies:
    xbmc.executebuiltin("Control.Move(9004,1)")
    xbmc.executebuiltin("Control.Move(9010,1)")
    # Reset countdown for movies:
    current_val = seed_val

# Save the updated countdown value for movies:
xbmc.executebuiltin(f"SetProperty(ItemListCountDownTimerMovie,{current_val},Home)")

# Conditionally log debugging messages for movies if logging is not disabled:
if logging_enabled:
    xbmc.log(f"Movie Timer - Seed: {seed_val}, Current: {current_val}", level=xbmc.LOGDEBUG)