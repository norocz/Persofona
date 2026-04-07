/* PersonDB — Matrix Rain + Network Graph */

// ============= Matrix Rain =============
(function initMatrixRain() {
  const canvas = document.getElementById('matrix-rain');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  let w, h, cols, drops;

  const chars = 'アイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホマミムメモヤユヨラリルレロワヲン0123456789ABCDEF';

  function resize() {
    w = canvas.width = window.innerWidth;
    h = canvas.height = window.innerHeight;
    cols = Math.floor(w / 18);
    drops = Array(cols).fill(1);
  }

  function draw() {
    ctx.fillStyle = 'rgba(0, 0, 0, 0.05)';
    ctx.fillRect(0, 0, w, h);
    ctx.fillStyle = '#00ff41';
    ctx.font = '14px "JetBrains Mono", monospace';

    for (let i = 0; i < cols; i++) {
      const char = chars[Math.floor(Math.random() * chars.length)];
      ctx.fillText(char, i * 18, drops[i] * 18);
      if (drops[i] * 18 > h && Math.random() > 0.975) {
        drops[i] = 0;
      }
      drops[i]++;
    }
  }

  resize();
  window.addEventListener('resize', resize);
  setInterval(draw, 55);
})();


// ============= Network Graph =============
function loadGraph() {
  const container = document.getElementById('network-graph');
  if (!container) return;

  fetch(container.dataset.url || '/api/graph/')
    .then(r => r.json())
    .then(data => renderGraph(container, data))
    .catch(() => {
      container.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;height:100%;color:#4a5f72;font-family:JetBrains Mono,monospace;font-size:0.85rem;">Žádná data pro graf</div>';
    });
}

function renderGraph(container, data) {
  if (!data.nodes.length) {
    container.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;height:100%;color:#4a5f72;font-family:JetBrains Mono,monospace;font-size:0.85rem;">Přidejte osoby a vztahy pro zobrazení grafu</div>';
    return;
  }

  const canvas = document.createElement('canvas');
  canvas.width = container.clientWidth || 800;
  canvas.height = container.clientHeight || 400;
  container.innerHTML = '';
  container.appendChild(canvas);
  const ctx = canvas.getContext('2d');
  const W = canvas.width, H = canvas.height;

  const typeColors = {
    parent: '#4fc3f7', child: '#4fc3f7', sibling: '#81c784', spouse: '#f06292',
    partner: '#f06292', friend: '#00ff41', bestfriend: '#ffeb3b', colleague: '#ff9800',
    boss: '#ff5722', enemy: '#f44336', acquaintance: '#78909c', other: '#607d8b',
    grandparent: '#4fc3f7', grandchild: '#4fc3f7', uncle_aunt: '#4fc3f7',
    cousin: '#4fc3f7', subordinate: '#ff9800', classmate: '#9c27b0',
    neighbor: '#8bc34a', mentor: '#00bcd4', mentee: '#00bcd4',
  };

  // Position nodes in a circle with some jitter
  const nodes = data.nodes.map((n, i) => {
    const angle = (2 * Math.PI * i) / data.nodes.length;
    const r = Math.min(W, H) * 0.35;
    return {
      ...n,
      x: W / 2 + r * Math.cos(angle) + (Math.random() - 0.5) * 40,
      y: H / 2 + r * Math.sin(angle) + (Math.random() - 0.5) * 40,
      vx: 0, vy: 0,
      radius: n.fav ? 22 : 16,
    };
  });

  const nodeMap = {};
  nodes.forEach(n => nodeMap[n.id] = n);

  const edges = data.edges.filter(e => nodeMap[e.from] && nodeMap[e.to]);

  // Simple force simulation
  function simulate() {
    const k = 0.008;
    const repulsion = 3000;
    const damping = 0.85;

    // Repulsion between all nodes
    for (let i = 0; i < nodes.length; i++) {
      for (let j = i + 1; j < nodes.length; j++) {
        const dx = nodes[j].x - nodes[i].x;
        const dy = nodes[j].y - nodes[i].y;
        const dist = Math.sqrt(dx * dx + dy * dy) || 1;
        const force = repulsion / (dist * dist);
        const fx = (dx / dist) * force;
        const fy = (dy / dist) * force;
        nodes[i].vx -= fx; nodes[i].vy -= fy;
        nodes[j].vx += fx; nodes[j].vy += fy;
      }
    }

    // Attraction along edges
    edges.forEach(e => {
      const a = nodeMap[e.from], b = nodeMap[e.to];
      if (!a || !b) return;
      const dx = b.x - a.x, dy = b.y - a.y;
      const dist = Math.sqrt(dx * dx + dy * dy) || 1;
      const force = (dist - 120) * k;
      const fx = (dx / dist) * force;
      const fy = (dy / dist) * force;
      a.vx += fx; a.vy += fy;
      b.vx -= fx; b.vy -= fy;
    });

    // Center gravity
    nodes.forEach(n => {
      n.vx += (W / 2 - n.x) * 0.001;
      n.vy += (H / 2 - n.y) * 0.001;
      n.vx *= damping;
      n.vy *= damping;
      n.x += n.vx;
      n.y += n.vy;
      n.x = Math.max(30, Math.min(W - 30, n.x));
      n.y = Math.max(30, Math.min(H - 30, n.y));
    });
  }

  function draw() {
    ctx.clearRect(0, 0, W, H);

    // Edges
    edges.forEach(e => {
      const a = nodeMap[e.from], b = nodeMap[e.to];
      if (!a || !b) return;
      ctx.beginPath();
      ctx.moveTo(a.x, a.y);
      ctx.lineTo(b.x, b.y);
      ctx.strokeStyle = (typeColors[e.type] || '#607d8b') + (e.active ? '60' : '25');
      ctx.lineWidth = e.active ? 1.5 : 0.8;
      ctx.stroke();
    });

    // Nodes
    nodes.forEach(n => {
      // Glow
      ctx.beginPath();
      ctx.arc(n.x, n.y, n.radius + 4, 0, Math.PI * 2);
      ctx.fillStyle = n.fav ? 'rgba(255,235,59,0.08)' : 'rgba(0,255,65,0.06)';
      ctx.fill();

      // Circle
      ctx.beginPath();
      ctx.arc(n.x, n.y, n.radius, 0, Math.PI * 2);
      ctx.fillStyle = '#111820';
      ctx.fill();
      ctx.strokeStyle = n.fav ? '#ffeb3b' : '#00ff41';
      ctx.lineWidth = n.fav ? 2.5 : 1.5;
      ctx.stroke();

      // Initials
      const initials = n.label.split(' ').map(w => w[0] || '').join('').toUpperCase().slice(0, 2);
      ctx.fillStyle = n.fav ? '#ffeb3b' : '#00ff41';
      ctx.font = `bold ${n.fav ? 11 : 9}px IBM Plex Sans, sans-serif`;
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText(initials, n.x, n.y);

      // Label below
      ctx.fillStyle = '#c9d6df';
      ctx.font = '10px "JetBrains Mono", monospace';
      ctx.fillText(n.label, n.x, n.y + n.radius + 12);
    });
  }

  // Run simulation
  let frame = 0;
  function tick() {
    simulate();
    draw();
    frame++;
    if (frame < 200) requestAnimationFrame(tick);
  }
  tick();

  // Click to navigate
  canvas.style.cursor = 'pointer';
  canvas.addEventListener('click', (ev) => {
    const rect = canvas.getBoundingClientRect();
    const mx = ev.clientX - rect.left, my = ev.clientY - rect.top;
    for (const n of nodes) {
      const dx = mx - n.x, dy = my - n.y;
      if (dx * dx + dy * dy < n.radius * n.radius * 1.5) {
        window.location.href = `/persons/${n.id}/`;
        return;
      }
    }
  });
}

// ============= Auto-dismiss alerts =============
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.alert').forEach(el => {
    setTimeout(() => el.style.opacity = '0', 4000);
    setTimeout(() => el.remove(), 4500);
  });
});
