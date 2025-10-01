import numpy as np
import matplotlib.pyplot as plt
import textwrap

# Parameters
n_cycles = 4
points_per_cycle = 300
p = 1.5
reset_frac = 0.5
adjust_frac = 0.25   # fraction of uncertainty drift to add to "adjusted expectations"

# Stepwise curve with resets
x_vals, y_vals = [], []
total_unc = 0.0
reset_points = []
drifts = []

for i in range(n_cycles):
    phase = np.linspace(0, 1, points_per_cycle)
    cycle_start = total_unc
    
    for j in range(1, len(phase)):
        step_inc = (phase[j] ** p) - (phase[j-1] ** p)
        total_unc += step_inc
        x_vals.append(i + phase[j])
        y_vals.append(total_unc)
    
    # reset / drop at end of cycle (skip last stage)
    if i < n_cycles - 1:
        cycle_growth = total_unc - cycle_start
        drop = (1 - reset_frac) * cycle_growth
        total_unc -= drop
        x_vals.append(i + 1)
        y_vals.append(total_unc)
        reset_points.append(i + 1)
        drifts.append(cycle_growth)

x_vals = np.array(x_vals)
y_vals = np.array(y_vals)

# Continual curve (no resets) – "fire and forget"
x_cont = np.linspace(0, n_cycles, n_cycles * points_per_cycle)
y_cont = x_cont ** p

# Interpolate y_vals onto x_cont so lengths match
y_step_interp = np.interp(x_cont, x_vals, y_vals)

# Adjusted expectations curve (stepwise increase at review points)
x_adj, y_adj = [0], [0]
current_adj = 0.0
for i in range(n_cycles):
    # span the cycle flat
    x_adj.extend(np.linspace(i, i+1, points_per_cycle))
    y_adj.extend([current_adj] * points_per_cycle)
    # at reset/review, bump expectations up
    if i < len(drifts):
        current_adj += adjust_frac * drifts[i]

x_adj = np.array(x_adj)
y_adj = np.array(y_adj)

# Stage names and descriptions
stages = [
    ("Functional\nRequirements", "Turn thoughts into statements of intent"),
    ("Technical\nSpecification", "Produce a detailed technical specification through iterative Q&A"),
    ("Development", "Develop code that meets the detailed technical specification"),
    ("Testing", "Develop code that generates synthetic data & tests to prove the code")
]

# Stage region boundaries: include start=0 and ends at resets + final stage end
stage_starts = [0] + reset_points
stage_ends = reset_points + [n_cycles]

# Plotting
fig, ax = plt.subplots(figsize=(12,6))

# Alternate shading of regions
for i in range(n_cycles):
    if i % 2 == 0:  # shaded
        ax.axvspan(stage_starts[i], stage_ends[i], color='gray', alpha=0.1)

# Vertical dotted lines at resets (skip last stage)
for rp in reset_points:
    ax.axvline(rp, color='gray', linestyle=':', linewidth=1)

# Shaded areas
# 1. Gap between actual uncertainty and adjusted expectations
ax.fill_between(x_vals, y_vals, np.interp(x_vals, x_adj, y_adj),
                color='skyblue', alpha=1, step='post',
                label='Expectations gap: actual uncertainty vs. adjusted expectations')
# 2. Extra drift above stepwise to fire-and-forget
ax.fill_between(x_cont, y_cont, y_step_interp,
                color='lightcoral', alpha=0.2,
                label='Additional uncertainty: the cost of fire-and-forget prompting')
# 3. Baseline to stepwise (when user never adjusts expectations)
ax.fill_between(x_vals, y_vals, 0,
                color='lightcoral', alpha=0.2, step='post',
                label='_nolegend_')
                #'Unacknowledged uncertainty (no review)')

# Curves
ax.plot(x_vals, y_vals, drawstyle='steps-post',
        label='Stepwise task specification, with human review & course correction', color='blue')
ax.plot(x_cont, y_cont,
        label='Single task specification, AI in total control from start to finish', color='red', linestyle='--')
ax.plot(x_adj, y_adj,
        label='User adjusted expectations (review-informed)', color='green')

# Review arrows (skip last stage)
s = ['Functional Requirements', 'Technical Specification', 'Development Code', 'Testing']
i = 0
for rp in reset_points:
    idx = np.searchsorted(x_vals, rp)
    ypos = y_vals[idx] if idx < len(y_vals) else y_vals[-1]
    ax.annotate(
        f"PM Review / Feedback\nof {s[i]}",
        xy=(rp, ypos),
        xytext=(rp, ypos + 0.5),
        arrowprops=dict(facecolor='black', arrowstyle='->'),
        ha='center',
        fontsize=9
    )
    i += 1

# X-axis labels: centered over each stage
stage_midpoints = [(start + end) / 2 for start, end in zip(stage_starts, stage_ends)]
ax.set_xticks(stage_midpoints)
ax.set_xticklabels([s[0] for s in stages], rotation=25, ha='right')

ax.yaxis.set_ticks([])

# Add descriptive text boxes above plot, aligned to stage centers
y_max = max(y_vals.max(), y_cont.max())
for i, (title, desc) in enumerate(stages):
    center = stage_midpoints[i]
    ax.text(center, y_max * 1.05, textwrap.fill(desc, 25), ha='center', va='bottom',
            fontsize=9, bbox=dict(facecolor='white', alpha=0.6, edgecolor='gray'))

# Scale so red line tops out just below the top
ax.set_ylim(0, y_max * 1.2)
ax.set_ylabel("Total Uncertainty ( | expectations - outcomes | )")
ax.set_title("Evolution of uncertainty of outcomes across development lifecycle")
ax.legend()
plt.tight_layout()
plt.savefig("../images/sawtooth_of_uncertainty.png", dpi=300, bbox_inches="tight")
plt.show()
