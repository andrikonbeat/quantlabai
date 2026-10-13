#!/usr/bin/env python3
"""
Final clean futuristic logos for QuantLab.
"""

# Gradient from the ANSI file (dark → teal → green → gold → purple)
GRADIENT = [
    (0x0d, 0x1b, 0x2a),  # dark navy
    (0x14, 0x33, 0x45),  # dark blue
    (0x1f, 0x4d, 0x5e),  # blue
    (0x2d, 0x6a, 0x7a),  # teal-blue
    (0x3a, 0x8f, 0x9a),  # teal
    (0x4e, 0xb8, 0x9f),  # mint-teal
    (0x6f, 0xd9, 0x9f),  # mint
    (0x95, 0xe8, 0xad),  # light green
    (0xb8, 0xf5, 0xc8),  # pale green
    (0xd4, 0xeb, 0x8a),  # yellow-green
    (0xeb, 0xd8, 0x6a),  # gold
    (0xf1, 0xca, 0x93),  # peach
    (0xeb, 0xbc, 0xba),  # mauve
    (0xc4, 0xa7, 0xe7),  # lavender
]

def get_palette(n=6):
    return [GRADIENT[i * len(GRADIENT) // n] for i in range(n)]

def simple_banner(width=60, height=8):
    """Clean gradient banner without text."""
    lines = []
    for row in range(height):
        line = "█" * width
        lines.append(line)
    return lines, get_palette()

def text_banner(width=60, height=10):
    """Gradient banner with QUANTLAB text."""
    
    # 5x5 font
    FONT = {
        'Q': ["████", "█  █", "█ ██", "█  █", "████"],
        'U': ["█  █", "█  █", "█  █", "█  █", "████"],
        'A': ["████", "█  █", "████", "█  █", "█  █"],
        'N': ["██ █", "█ ██", "█  █", "█  █", "█  █"],
        'T': ["█████", "  █  ", "  █  ", "  █  ", "  █  "],
        'L': ["█    ", "█    ", "█    ", "█    ", "████"],
        'B': ["████", "█  █", "████", "█  █", "████"],
    }
    
    text = "QUANTLAB"
    cw = 5  # 4 + 1 space
    tw = len(text) * cw - 1
    
    lines = []
    for row in range(height):
        color_idx = min(row * len(GRADIENT) // height, len(GRADIENT) - 1)
        
        line = []
        left_pad = (width - (tw)) // 2
        # Left padding with subtle pattern
        for c in range(left_pad):
            line.append("▀" if (c + row) % 4 == 0 else " ")
        
        # Text
        for ci, ch in enumerate(text):
            if 0 <= row < 5:
                pattern = FONT.get(ch, ["█" * 4] * 5)[row]
                for px, pc in enumerate(pattern):
                    line.append("█" if pc == '█' else " ")
            if ci < len(text) - 1:
                line.append(" ")
        
        # Right padding
        right_pad = width - len(line)
        for c in range(right_pad):
            line.append("▄" if (c + row) % 4 == 0 else " ")
        
        lines.append("".join(line))
    
    return lines, get_palette()

def generate_go(lines, palette, name):
    pal = [f'        lipgloss.Color("#{r:02x}{g:02x}{b:02x}"),' for r,g,b in palette]
    lns = [f'        "{ln}",' for ln in lines]
    return f'''// Code generated - DO NOT EDIT
package theme

import (
	"strings"
	"github.com/charmbracelet/lipgloss"
)

var {name}LogoLines = []string{{
{chr(10).join(lns)}
}}

var {name}GradientColors = []lipgloss.Color{{{chr(10).join(pal)}
}}

func Render{name.title()}Logo() string {{
	total := len({name}LogoLines)
	if total == 0 {{ return "" }}
	bands := len({name}GradientColors)
	var b strings.Builder
	for i, line := range {name}LogoLines {{
		bandIdx := (i * bands) / total
		if bandIdx >= bands {{ bandIdx = bands - 1 }}
		style := lipgloss.NewStyle().Foreground({name}GradientColors[bandIdx])
		b.WriteString(style.Render(line))
		if i < total-1 {{ b.WriteByte('\\n') }}
	}}
	return b.String()
}}
'''

if __name__ == "__main__":
    # Simple banner
    l1, p1 = simple_banner(60, 8)
    print("=== FUTURISTIC (simple) ===")
    print(generate_go(l1, p1, "futuristic"))
    
    # Text banner
    l2, p2 = text_banner(60, 10)
    print("\n=== FUTURISTICTEXT (with QUANTLAB) ===")
    print(generate_go(l2, p2, "futuristicText"))
