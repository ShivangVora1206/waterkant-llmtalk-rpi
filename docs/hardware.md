# Hardware Guide

## Tested Microphones

| Device | Quality | Notes |
|---|---|---|
| Blue Snowball iCE | Good | Simple plug-and-play, no drivers needed |
| Rode NT-USB Mini | Excellent | Best SNR tested; cardioid pattern |
| ReSpeaker USB 4-Mic Array | Good | Far-field pickup; good for desk use |
| Generic USB desk mic | Fair | Works; may need VAD threshold tuning |

## Tested Speakers

| Device | Notes |
|---|---|
| 3.5 mm analog jack | Pi 5 has a 3.5 mm combo jack; quality is OK |
| USB-powered portable speaker | Recommended; powered via USB-A on Pi |
| USB-C DAC + headphones | Best audio quality |
| HDMI monitor with speakers | Works for desktop use |

## Audio Configuration Tips

- If you use a USB mic and USB speaker simultaneously, ALSA may assign them the same device index on different boots. Pin them by name in Settings → Audio to avoid surprises.
- A ground loop hum may appear when using the 3.5 mm jack alongside USB devices. Use a USB speaker to avoid it.
- The Pi 5's 3.5 mm jack is output-only. For the mic, a USB device is required.

## GPIO (Optional)

### Push-to-Talk Button (GPIO 17)
Connect a momentary switch between GPIO 17 and GND. Enable via config:
```yaml
# Not yet exposed in dashboard — edit configs/runtime.json:
gpio_ptt:
  enabled: true
  pin: 17
```

### LED Status Indicator (GPIO 18)
Connect an LED with a 330Ω resistor between GPIO 18 and GND.
States: off=IDLE, solid=LISTENING/SPEAKING, blink fast=ERROR, blink slow=PAUSED.

## Recommended Accessories

- **Heatsink + fan**: Required for sustained inference loads (prevents thermal throttling)
- **Official Pi 5 27W PSU**: Ensures stable power under USB + CPU load
- **64 GB+ A2 microSD or NVMe SSD via PCIe**: Faster model loading, more swap space
