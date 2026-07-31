import matplotlib.pyplot as plt
import numpy as np

subsets = ['Reactive', 'Proactive\nStrong', 'Proactive\nMedium', 'Proactive\nWeak', 'Speech\nInterrupt', 'Tool\nInterrupt', 'Tool-Int\nExtra']

text_pass = [80, 38, 36, 45, 12, 54, 9]
voice_pass = [35, 9, 15, 39, 4, 17, 3]
text_n  = [99, 120, 120, 60, 33, 75, 12]
voice_n = [100, 120, 120, 60, 33, 75, 12]
text_rate  = [100*p/n for p,n in zip(text_pass, text_n)]
voice_rate = [100*p/n for p,n in zip(voice_pass, voice_n)]
delta = [tr-vr for tr,vr in zip(text_rate, voice_rate)]

cats = ['ASR', 'Premature', 'Param err', 'Missing', 'Unexpected', 'Wrong tool']
text_fails = [
    [1,9,7,5,0,0], [1,22,25,39,0,0], [3,31,21,37,0,0],
    [0,0,0,0,15,0], [0,18,1,8,0,3], [1,16,0,4,0,1], [0,2,0,0,0,1],
]
voice_fails = [
    [38,19,12,1,0,0], [33,22,37,29,0,0], [19,34,28,33,0,0],
    [0,0,0,0,21,0], [17,25,8,5,0,7], [34,32,9,2,0,0], [4,4,4,0,0,0],
]
colors_f = ['#D32F2F', '#FB8C00', '#FDD835', '#78909C', '#8E24AA', '#00838F']

fig, axes = plt.subplots(2, 1, figsize=(14, 10))

ax1 = axes[0]
x = np.arange(len(subsets))
w = 0.38
b1 = ax1.bar(x-w/2, text_rate,  w, label='Text',  color='#2E7D32', edgecolor='black', linewidth=0.5)
b2 = ax1.bar(x+w/2, voice_rate, w, label='Voice', color='#C62828', edgecolor='black', linewidth=0.5)
for i,(tr,vr,d) in enumerate(zip(text_rate, voice_rate, delta)):
    ax1.annotate(f'{tr:.1f}%', xy=(i-w/2, tr+1), ha='center', fontsize=9)
    ax1.annotate(f'{vr:.1f}%', xy=(i+w/2, vr+1), ha='center', fontsize=9)
    ax1.annotate(f'Δ+{d:.1f}', xy=(i, max(tr,vr)+7), ha='center', fontsize=10, fontweight='bold', color='#1A237E')
ax1.set_xticks(x); ax1.set_xticklabels(subsets)
ax1.set_ylabel('Pass rate (%)', fontsize=11)
ax1.set_title('Pass rate: Text vs Voice (same gpt-realtime, 520 matched tasks)', fontsize=12, fontweight='bold')
ax1.legend(loc='upper right', fontsize=11)
ax1.set_ylim(0, 100)
ax1.grid(axis='y', alpha=0.3)
ax1.axhline(y=52.8, color='#2E7D32', linestyle=':', linewidth=1, alpha=0.6)
ax1.axhline(y=23.5, color='#C62828', linestyle=':', linewidth=1, alpha=0.6)
ax1.text(6.5, 52.8+1, 'Text overall 52.8%', fontsize=8, color='#2E7D32', ha='right')
ax1.text(6.5, 23.5+1, 'Voice overall 23.5%', fontsize=8, color='#C62828', ha='right')

ax2 = axes[1]
text_arr  = np.array(text_fails).T
voice_arr = np.array(voice_fails).T
bottom_t = np.zeros(len(subsets)); bottom_v = np.zeros(len(subsets))
for i, cat in enumerate(cats):
    ax2.bar(x-w/2, text_arr[i],  w, bottom=bottom_t, color=colors_f[i], label=cat, edgecolor='white', linewidth=0.3)
    ax2.bar(x+w/2, voice_arr[i], w, bottom=bottom_v, color=colors_f[i], edgecolor='white', linewidth=0.3)
    bottom_t += text_arr[i]; bottom_v += voice_arr[i]
for i in range(len(subsets)):
    ax2.text(i-w/2, -3.5, 'T', ha='center', fontsize=10, fontweight='bold', color='#2E7D32')
    ax2.text(i+w/2, -3.5, 'V', ha='center', fontsize=10, fontweight='bold', color='#C62828')
    ax2.text(i-w/2, bottom_t[i]+1, str(int(bottom_t[i])), ha='center', fontsize=8)
    ax2.text(i+w/2, bottom_v[i]+1, str(int(bottom_v[i])), ha='center', fontsize=8)
ax2.set_xticks(x); ax2.set_xticklabels(subsets)
ax2.set_ylabel('Failure count (per-tool attributions)', fontsize=11)
ax2.set_title('Failure attribution: Text (T) vs Voice (V)', fontsize=12, fontweight='bold')
ax2.legend(loc='upper right', fontsize=10, ncol=2)
ax2.grid(axis='y', alpha=0.3)
ax2.set_ylim(-8, max(bottom_t.max(), bottom_v.max())*1.15)

plt.tight_layout()
out = '/tmp/text_vs_voice_analysis.png'
plt.savefig(out, dpi=140, bbox_inches='tight')
print(f"saved: {out}")
