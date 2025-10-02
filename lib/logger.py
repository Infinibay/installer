"""
Colored logging system for the Infinibay installer.
Uses ANSI escape codes for terminal output formatting.
"""

import sys
import time

# ANSI color codes
RESET = '\033[0m'
BOLD = '\033[1m'
RED = '\033[91m'
GREEN = '\033[92m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
CYAN = '\033[96m'
GRAY = '\033[90m'

# Symbols for visual clarity
SUCCESS = '✓'
ERROR = '✗'
WARNING = '⚠'
INFO = 'ℹ'
STEP = '→'

# Global state
verbose_mode = False


def setup_logger(verbose: bool = False):
    """Initialize logging configuration."""
    global verbose_mode
    verbose_mode = verbose


def log_info(message: str):
    """Log informational message in blue."""
    print(f"{BLUE}{INFO}{RESET} {message}")


def log_success(message: str):
    """Log success message in green."""
    print(f"{GREEN}{SUCCESS}{RESET} {message}")


def log_warning(message: str):
    """Log warning message in yellow."""
    print(f"{YELLOW}{WARNING}{RESET} {message}")


def log_error(message: str):
    """Log error message in red to stderr."""
    print(f"{RED}{ERROR}{RESET} {message}", file=sys.stderr)


def log_step(step_number: int, total_steps: int, message: str):
    """Log step progress in cyan with bold numbers."""
    print(f"{CYAN}{STEP}{RESET} {BOLD}Step {step_number}/{total_steps}:{RESET} {message}")


def log_debug(message: str):
    """Log debug message in gray (only if verbose mode)."""
    if verbose_mode:
        print(f"{GRAY}[DEBUG]{RESET} {message}")


def log_command(command: str):
    """Log command being executed (only if verbose mode)."""
    if verbose_mode:
        print(f"{GRAY}$ {command}{RESET}")


def print_animated_waves():
    """Print animated ocean waves effect (Infinite Bay concept)."""
    try:
        # Try to use asciimatics for better animation
        from asciimatics.screen import Screen
        from asciimatics.effects import Print
        from asciimatics.renderers import FigletText, Rainbow
        from asciimatics.scene import Scene
        from asciimatics.exceptions import ResizeScreenError
        import math

        def demo(screen):
            # Wave pattern using unicode characters
            wave_chars = ['~', '≈', '∼', '～']

            # Create wave lines
            scenes = []
            effects = []

            # Animated waves at bottom
            for y in range(screen.height - 8, screen.height):
                wave_line = ""
                for x in range(screen.width):
                    # Create wave pattern based on position
                    wave_index = int((x + y * 3) / 4) % len(wave_chars)
                    wave_line += wave_chars[wave_index]
                effects.append(
                    Print(screen,
                          Rainbow(screen, FigletText(wave_line[:20], font='banner')),
                          y=y,
                          x=0,
                          colour=Screen.COLOUR_CYAN)
                )

            # Main title
            effects.append(
                Print(screen,
                      Rainbow(screen, FigletText("INFINIBAY", font='banner3')),
                      y=screen.height // 2 - 8,
                      x=(screen.width - 60) // 2,
                      colour=Screen.COLOUR_CYAN)
            )

            scenes.append(Scene(effects, 60))  # 60 frames (about 3 seconds)
            screen.play(scenes, stop_on_resize=True)

        Screen.wrapper(demo)

    except ImportError:
        # Fallback to simple wave animation if asciimatics not available
        print_simple_wave_animation()
    except ResizeScreenError:
        # If screen resized, just show static banner
        print_banner()
    except Exception:
        # Any other error, show static banner
        print_banner()


def print_simple_wave_animation():
    """Fallback animation using only ANSI codes (no external dependencies)."""
    # Clear screen
    print("\033[2J\033[H", end='')

    # Wave characters
    wave_frames = [
        "～～～～～～～～～～～～～～～～～～～～～～～～～～～～～～",
        "∼∼∼∼∼∼∼∼∼∼∼∼∼∼∼∼∼∼∼∼∼∼∼∼∼∼∼∼∼∼",
        "≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈≈",
        "~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~",
    ]

    title_lines = [
        "  ██╗███╗   ██╗███████╗██╗███╗   ██╗██╗██████╗  █████╗ ██╗   ██╗",
        "  ██║████╗  ██║██╔════╝██║████╗  ██║██║██╔══██╗██╔══██╗╚██╗ ██╔╝",
        "  ██║██╔██╗ ██║█████╗  ██║██╔██╗ ██║██║██████╔╝███████║ ╚████╔╝ ",
        "  ██║██║╚██╗██║██╔══╝  ██║██║╚██╗██║██║██╔══██╗██╔══██║  ╚██╔╝  ",
        "  ██║██║ ╚████║██║     ██║██║ ╚████║██║██████╔╝██║  ██║   ██║   ",
        "  ╚═╝╚═╝  ╚═══╝╚═╝     ╚═╝╚═╝  ╚═══╝╚═╝╚═════╝ ╚═╝  ╚═╝   ╚═╝   ",
    ]

    # Animate 3 wave cycles
    for cycle in range(3):
        for frame_idx, wave in enumerate(wave_frames):
            # Move cursor to top
            print("\033[H", end='')

            # Print top waves
            print(f"{BLUE}{wave}{RESET}")
            print(f"{CYAN}{wave_frames[(frame_idx + 1) % len(wave_frames)]}{RESET}")
            print()

            # Print title with gradient effect
            for i, line in enumerate(title_lines):
                color = CYAN if i % 2 == 0 else BLUE
                print(f"{color}{BOLD}{line}{RESET}")

            print()
            print(f"{CYAN}{'  ' * 10}🌊 Infinite Bay - Virtualization Platform 🌊{RESET}")
            print(f"{BLUE}{'  ' * 14}Automated Installer{RESET}")
            print()

            # Print bottom waves
            print(f"{CYAN}{wave_frames[(frame_idx + 2) % len(wave_frames)]}{RESET}")
            print(f"{BLUE}{wave}{RESET}")

            sys.stdout.flush()
            time.sleep(0.15)

    # Hold final frame for a moment
    time.sleep(0.5)


def print_banner():
    """Print static ASCII art banner with Infinibay logo."""
    banner = f"""
{CYAN}{BOLD}
╔═══════════════════════════════════════════════════════════════════╗
║                                                                   ║
║   ██╗███╗   ██╗███████╗██╗███╗   ██╗██╗██████╗  █████╗ ██╗   ██╗  ║
║   ██║████╗  ██║██╔════╝██║████╗  ██║██║██╔══██╗██╔══██╗╚██╗ ██╔╝  ║
║   ██║██╔██╗ ██║█████╗  ██║██╔██╗ ██║██║██████╔╝███████║ ╚████╔╝   ║
║   ██║██║╚██╗██║██╔══╝  ██║██║╚██╗██║██║██╔══██╗██╔══██║  ╚██╔╝    ║
║   ██║██║ ╚████║██║     ██║██║ ╚████║██║██████╔╝██║  ██║   ██║     ║
║   ╚═╝╚═╝  ╚═══╝╚═╝     ╚═╝╚═╝  ╚═══╝╚═╝╚═════╝ ╚═╝  ╚═╝   ╚═╝     ║
║                                                                   ║
║         🌊 Infinite Bay - Virtualization Platform 🌊              ║
║                   Automated Installer                             ║
║                                                                   ║
╚═══════════════════════════════════════════════════════════════════╝
{RESET}
                         Version 1.0.0
"""
    print(banner)
