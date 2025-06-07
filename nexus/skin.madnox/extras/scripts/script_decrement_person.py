import xbmc

# Check if logging is disabled (skin setting)
logging_enabled = xbmc.getInfoLabel("Skin.HasSetting(disablecounterscriptloggingall)").lower() == 'true'

# Fetch the "seed" (in seconds) from a Kodi skin string for persons:
seed_str = xbmc.getInfoLabel("Skin.String(personmetascrollingdelayvaluevarb)")
try:
    seed_val = int(seed_str)
except ValueError:
    seed_val = 7  # fallback if user typed something invalid

# Read the current countdown value for persons:
current_str = xbmc.getInfoLabel("Window(Home).Property(ItemListCountDownTimerPerson)")
try:
    current_val = int(current_str)
except ValueError:
    current_val = seed_val

# Decrement or reset the countdown for persons:
if current_val > 0:
    current_val -= 1
else:
    # We hit 0, so do the Move() animation for persons:
    xbmc.executebuiltin("Control.Move(9002,1)")
    # Reset countdown for persons:
    current_val = seed_val

# Save the updated countdown value for persons:
xbmc.executebuiltin(f"SetProperty(ItemListCountDownTimerPerson,{current_val},Home)")

# Debugging logs for persons (optional):
if logging_enabled:
    xbmc.log(f"Person Timer - Seed: {seed_val}, Current: {current_val}", level=xbmc.LOGDEBUG)
