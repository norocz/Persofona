/* PersonDB — Full-page Network Map
   Features: group clusters, tag coloring, pan/zoom, tooltips, physics toggle */

(function() {
  'use strict';

  const canvas = document.getElementById('fullmap');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');

  // --- State ---
  let nodes = [], edges = [], groups = [], tags = [];
  let showGroups = true, showLabels = true, physicsRunning = true;
  let scale = 1, offsetX = 0, offsetY = 0;
  let dragNode = null, isPanning = false, panStart = {x:0, y:0};
  let hoveredNode = null;
  let activeFilter = null; // 'group:id' or 'tag:id'
  let W, H;

  const REL_COLORS = {
    parent:'#4fc3f7', child:'#4fc3f7', sibling:'#81c784', spouse:'#f06292',
    partner:'#f06292', friend:'#00ff41', bestfriend:'#ffeb3b', colleague:'#ff9800',
    boss:'#ff5722', enemy:'#f44336', acquaintance:'#78909c', other:'#607d8b',
    grandparent:'#4fc3f7', grandchild:'#4fc3f7', uncle_aunt:'#4fc3f7',
    cousin:'#4fc3f7', subordinate:'#ff9800', classmate:'#9c27b0',
    neighbor:'#8bc34a', mentor:'#00bcd4', mentee:'#00bcd4',
  };

  const REL_LABELS = {
    parent:'Rodič', child:'Dítě', sibling:'Sourozenec', spouse:'Manžel/ka',
    partner:'Partner/ka', friend:'Přítel', bestfriend:'Nejlepší přítel',
    colleague:'Kolega', boss:'Nadřízený', subordinate:'Podřízený',
    classmate:'Spolužák', neighbor:'Soused', acquaintance:'Známý',
    enemy:'Nepřítel', mentor:'Mentor', mentee:'Mentee', other:'Jiný',
    grandparent:'Prarodič', grandchild:'Vnuk/vnučka', uncle_aunt:'Strýc/teta', cousin:'Bratranec',
  };

  // --- Resize ---
  function resize() {
    const rect = canvas.parentElement.getBoundingClientRect();
    W = canvas.width = rect.width;
    H = canvas.height = rect.height;
  }

  // --- Load data ---
  function loadData() {
    fetch(GRAPH_DATA_URL)
      .then(r => r.json())
      .then(data => {
        groups = data.groups || [];
        tags = data.tags || [];

        // Build nodes with positions
        const count = data.nodes.length;
        nodes = data.nodes.map((n, i) => {
          const angle = (2 * Math.PI * i) / Math.max(count, 1);
          const r = Math.min(W, H) * 0.35;
          return {
            ...n,
            x: W/2 + r * Math.cos(angle) + (Math.random() - 0.5) * 60,
            y: H/2 + r * Math.sin(angle) + (Math.random() - 0.5) * 60,
            vx: 0, vy: 0,
            radius: n.fav ? 24 : 18,
            visible: true,
          };
        });

        const nodeMap = {};
        nodes.forEach(n => nodeMap[n.id] = n);
        edges = data.edges.filter(e => nodeMap[e.from] && nodeMap[e.to]).map(e => ({
          ...e, a: nodeMap[e.from], b: nodeMap[e.to]
        }));

        // Position nodes by groups if they have them
        positionByGroups();
        buildLegend();
        buildFilters();
        tick();
      })
      .catch(err => {
        ctx.fillStyle = '#4a5f72';
        ctx.font = '14px JetBrains Mono, monospace';
        ctx.textAlign = 'center';
        ctx.fillText('Chyba při načítání dat', W/2, H/2);
      });
  }

  // --- Position nodes by group clusters ---
  function positionByGroups() {
    if (!groups.length || !nodes.length) return;

    const groupMap = {};
    groups.forEach((g, i) => {
      const angle = (2 * Math.PI * i) / groups.length;
      const r = Math.min(W, H) * 0.28;
      groupMap[g.id] = {
        cx: W/2 + r * Math.cos(angle),
        cy: H/2 + r * Math.sin(angle),
        ...g,
      };
    });

    nodes.forEach(n => {
      if (n.group_ids && n.group_ids.length > 0) {
        // Average position of all groups this person belongs to
        let cx = 0, cy = 0, cnt = 0;
        n.group_ids.forEach(gid => {
          const gp = groupMap[gid];
          if (gp) { cx += gp.cx; cy += gp.cy; cnt++; }
        });
        if (cnt > 0) {
          n.x = cx/cnt + (Math.random() - 0.5) * 80;
          n.y = cy/cnt + (Math.random() - 0.5) * 80;
        }
      }
    });
  }

  // --- Physics simulation ---
  function simulate() {
    if (!physicsRunning) return;
    const repulsion = 4500;
    const edgeK = 0.006;
    const damping = 0.88;
    const groupPull = 0.003;

    // Group centers for cluster gravity
    const groupCenters = {};
    groups.forEach((g, i) => {
      const angle = (2 * Math.PI * i) / groups.length;
      const r = Math.min(W, H) * 0.28;
      groupCenters[g.id] = { cx: W/2 + r * Math.cos(angle), cy: H/2 + r * Math.sin(angle) };
    });

    // Repulsion
    for (let i = 0; i < nodes.length; i++) {
      if (!nodes[i].visible) continue;
      for (let j = i+1; j < nodes.length; j++) {
        if (!nodes[j].visible) continue;
        const dx = nodes[j].x - nodes[i].x;
        const dy = nodes[j].y - nodes[i].y;
        const dist = Math.sqrt(dx*dx + dy*dy) || 1;
        const f = repulsion / (dist * dist);
        const fx = (dx/dist)*f, fy = (dy/dist)*f;
        nodes[i].vx -= fx; nodes[i].vy -= fy;
        nodes[j].vx += fx; nodes[j].vy += fy;
      }
    }

    // Edge attraction
    edges.forEach(e => {
      if (!e.a.visible || !e.b.visible) return;
      const dx = e.b.x - e.a.x, dy = e.b.y - e.a.y;
      const dist = Math.sqrt(dx*dx + dy*dy) || 1;
      const f = (dist - 140) * edgeK;
      const fx = (dx/dist)*f, fy = (dy/dist)*f;
      e.a.vx += fx; e.a.vy += fy;
      e.b.vx -= fx; e.b.vy -= fy;
    });

    // Group cluster gravity
    if (showGroups) {
      nodes.forEach(n => {
        if (!n.visible || !n.group_ids) return;
        n.group_ids.forEach(gid => {
          const gc = groupCenters[gid];
          if (gc) {
            n.vx += (gc.cx - n.x) * groupPull;
            n.vy += (gc.cy - n.y) * groupPull;
          }
        });
      });
    }

    // Center gravity + damping + bounds
    nodes.forEach(n => {
      if (!n.visible) return;
      n.vx += (W/2 - n.x) * 0.0004;
      n.vy += (H/2 - n.y) * 0.0004;
      n.vx *= damping; n.vy *= damping;
      if (dragNode !== n) {
        n.x += n.vx; n.y += n.vy;
      }
      n.x = Math.max(40, Math.min(W-40, n.x));
      n.y = Math.max(40, Math.min(H-40, n.y));
    });
  }

  // --- Draw ---
  function draw() {
    ctx.save();
    ctx.clearRect(0, 0, W, H);
    ctx.translate(offsetX, offsetY);
    ctx.scale(scale, scale);

    // Draw group hulls
    if (showGroups && groups.length) {
      groups.forEach(g => {
        const members = nodes.filter(n => n.visible && n.group_ids && n.group_ids.includes(g.id));
        if (members.length < 2) return;

        // Compute bounding box
        let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
        members.forEach(n => {
          if (n.x < minX) minX = n.x; if (n.y < minY) minY = n.y;
          if (n.x > maxX) maxX = n.x; if (n.y > maxY) maxY = n.y;
        });
        const pad = 50;
        const cx = (minX+maxX)/2, cy = (minY+maxY)/2;
        const rx = (maxX-minX)/2 + pad, ry = (maxY-minY)/2 + pad;

        // Draw ellipse hull
        ctx.beginPath();
        ctx.ellipse(cx, cy, Math.max(rx, 60), Math.max(ry, 50), 0, 0, Math.PI*2);
        ctx.fillStyle = (g.color || '#00ff41') + '0a';
        ctx.fill();
        ctx.strokeStyle = (g.color || '#00ff41') + '30';
        ctx.lineWidth = 1.5;
        ctx.setLineDash([6, 4]);
        ctx.stroke();
        ctx.setLineDash([]);

        // Group label
        if (showLabels) {
          ctx.fillStyle = (g.color || '#00ff41') + '80';
          ctx.font = 'bold 11px IBM Plex Sans, sans-serif';
          ctx.textAlign = 'center';
          ctx.fillText(g.name.toUpperCase(), cx, minY - pad + 12);
        }
      });
    }

    // Draw edges
    edges.forEach(e => {
      if (!e.a.visible || !e.b.visible) return;
      ctx.beginPath();
      ctx.moveTo(e.a.x, e.a.y);
      ctx.lineTo(e.b.x, e.b.y);
      const eColor = REL_COLORS[e.type] || '#607d8b';
      ctx.strokeStyle = eColor + (e.active !== false ? '50' : '20');
      ctx.lineWidth = e.active !== false ? 1.5 : 0.8;
      ctx.stroke();

      // Edge label on hover
      if (showLabels && scale > 0.7) {
        const mx = (e.a.x + e.b.x) / 2, my = (e.a.y + e.b.y) / 2;
        ctx.fillStyle = eColor + '60';
        ctx.font = '8px JetBrains Mono, monospace';
        ctx.textAlign = 'center';
        ctx.fillText(REL_LABELS[e.type] || e.type, mx, my - 4);
      }
    });

    // Draw nodes
    nodes.forEach(n => {
      if (!n.visible) return;
      const isHovered = hoveredNode === n;
      const r = n.radius * (isHovered ? 1.15 : 1);

      // Glow
      ctx.beginPath();
      ctx.arc(n.x, n.y, r + 6, 0, Math.PI*2);
      ctx.fillStyle = n.fav ? 'rgba(255,235,59,0.06)' : 'rgba(0,255,65,0.04)';
      if (isHovered) ctx.fillStyle = 'rgba(0,255,65,0.12)';
      ctx.fill();

      // Determine node color from first tag
      let nodeColor = n.fav ? '#ffeb3b' : '#00ff41';
      if (n.tag_colors && n.tag_colors.length > 0) {
        nodeColor = n.tag_colors[0];
      }

      // Photo circle or initials
      ctx.beginPath();
      ctx.arc(n.x, n.y, r, 0, Math.PI*2);
      ctx.fillStyle = '#111820';
      ctx.fill();
      ctx.strokeStyle = nodeColor;
      ctx.lineWidth = isHovered ? 3 : (n.fav ? 2.5 : 1.5);
      ctx.stroke();

      // Initials
      const initials = n.label.split(' ').map(w => w[0]||'').join('').toUpperCase().slice(0,2);
      ctx.fillStyle = nodeColor;
      ctx.font = `bold ${n.fav ? 13 : 10}px IBM Plex Sans, sans-serif`;
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText(initials, n.x, n.y);

      // Label below
      if (showLabels) {
        ctx.fillStyle = isHovered ? '#ffffff' : '#c9d6df';
        ctx.font = `${isHovered ? '12' : '10'}px JetBrains Mono, monospace`;
        ctx.textAlign = 'center';
        ctx.textBaseline = 'top';
        ctx.fillText(n.label, n.x, n.y + r + 5);
      }

      // Favorite star
      if (n.fav) {
        ctx.fillStyle = '#ffeb3b';
        ctx.font = '10px sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('★', n.x + r - 2, n.y - r + 2);
      }

      // Tag dots ring
      if (n.tag_colors && n.tag_colors.length > 1) {
        n.tag_colors.forEach((tc, i) => {
          const a = (2 * Math.PI * i) / n.tag_colors.length - Math.PI/2;
          const dx = (r + 10) * Math.cos(a);
          const dy = (r + 10) * Math.sin(a);
          ctx.beginPath();
          ctx.arc(n.x + dx, n.y + dy, 3, 0, Math.PI*2);
          ctx.fillStyle = tc;
          ctx.fill();
        });
      }
    });

    ctx.restore();
  }

  // --- Animation loop ---
  let frame = 0;
  function tick() {
    simulate();
    draw();
    frame++;
    requestAnimationFrame(tick);
  }

  // --- Tooltip ---
  const tooltip = document.getElementById('tooltip');
  const ttName = document.getElementById('tt-name');
  const ttInfo = document.getElementById('tt-info');
  const ttTags = document.getElementById('tt-tags');

  function showTooltip(node, mx, my) {
    ttName.textContent = node.label;
    let info = [];
    if (node.company) info.push(node.company);
    if (node.job_title) info.push(node.job_title);
    const relCount = edges.filter(e => e.a === node || e.b === node).length;
    info.push(relCount + ' vztahů');
    ttInfo.textContent = info.join(' · ');

    ttTags.innerHTML = '';
    if (node.tag_names) {
      node.tag_names.forEach((tn, i) => {
        const el = document.createElement('span');
        el.className = 'tt-tag';
        el.textContent = tn;
        const c = (node.tag_colors && node.tag_colors[i]) || '#00ff41';
        el.style.background = c + '25';
        el.style.color = c;
        el.style.border = '1px solid ' + c + '40';
        ttTags.appendChild(el);
      });
    }

    tooltip.style.left = (mx + 16) + 'px';
    tooltip.style.top = (my - 10) + 'px';
    tooltip.style.display = 'block';
  }

  function hideTooltip() { tooltip.style.display = 'none'; }

  // --- Mouse to canvas coords ---
  function canvasCoords(e) {
    const rect = canvas.getBoundingClientRect();
    return {
      x: (e.clientX - rect.left - offsetX) / scale,
      y: (e.clientY - rect.top - offsetY) / scale,
    };
  }

  function screenCoords(e) {
    const rect = canvas.getBoundingClientRect();
    return { x: e.clientX - rect.left, y: e.clientY - rect.top };
  }

  function findNode(cx, cy) {
    for (let i = nodes.length - 1; i >= 0; i--) {
      const n = nodes[i];
      if (!n.visible) continue;
      const dx = cx - n.x, dy = cy - n.y;
      if (dx*dx + dy*dy < n.radius * n.radius * 1.5) return n;
    }
    return null;
  }

  // --- Mouse events ---
  canvas.addEventListener('mousedown', e => {
    const c = canvasCoords(e);
    const node = findNode(c.x, c.y);
    if (node) {
      dragNode = node;
      canvas.style.cursor = 'grabbing';
    } else {
      isPanning = true;
      panStart = { x: e.clientX - offsetX, y: e.clientY - offsetY };
      canvas.style.cursor = 'grabbing';
    }
  });

  canvas.addEventListener('mousemove', e => {
    const c = canvasCoords(e);
    const s = screenCoords(e);

    if (dragNode) {
      dragNode.x = c.x;
      dragNode.y = c.y;
      dragNode.vx = 0; dragNode.vy = 0;
    } else if (isPanning) {
      offsetX = e.clientX - panStart.x;
      offsetY = e.clientY - panStart.y;
    } else {
      const node = findNode(c.x, c.y);
      if (node) {
        canvas.style.cursor = 'pointer';
        hoveredNode = node;
        showTooltip(node, s.x, s.y);
      } else {
        canvas.style.cursor = 'grab';
        hoveredNode = null;
        hideTooltip();
      }
    }
  });

  canvas.addEventListener('mouseup', () => {
    dragNode = null;
    isPanning = false;
    canvas.style.cursor = hoveredNode ? 'pointer' : 'grab';
  });

  canvas.addEventListener('mouseleave', () => {
    dragNode = null; isPanning = false; hoveredNode = null;
    hideTooltip();
  });

  // Click to navigate
  canvas.addEventListener('click', e => {
    if (dragNode) return;
    const c = canvasCoords(e);
    const node = findNode(c.x, c.y);
    if (node) {
      window.location.href = '/persons/' + node.id + '/';
    }
  });

  // Scroll to zoom
  canvas.addEventListener('wheel', e => {
    e.preventDefault();
    const factor = e.deltaY < 0 ? 1.1 : 0.9;
    const rect = canvas.getBoundingClientRect();
    const mx = e.clientX - rect.left, my = e.clientY - rect.top;
    offsetX = mx - (mx - offsetX) * factor;
    offsetY = my - (my - offsetY) * factor;
    scale *= factor;
    scale = Math.max(0.2, Math.min(4, scale));
  }, { passive: false });

  // --- Controls ---
  window.graphZoom = function(factor) {
    const cx = W/2, cy = H/2;
    offsetX = cx - (cx - offsetX) * factor;
    offsetY = cy - (cy - offsetY) * factor;
    scale *= factor;
    scale = Math.max(0.2, Math.min(4, scale));
  };

  window.graphReset = function() {
    scale = 1; offsetX = 0; offsetY = 0;
    activeFilter = null;
    nodes.forEach(n => n.visible = true);
    document.querySelectorAll('.filter-chip').forEach(c => c.classList.remove('active'));
  };

  window.togglePhysics = function() {
    physicsRunning = !physicsRunning;
    document.getElementById('btn-physics').textContent = physicsRunning ? '▶' : '⏸';
    document.getElementById('btn-physics').style.color = physicsRunning ? 'var(--green)' : 'var(--amber)';
  };

  window.toggleGroups = function() {
    showGroups = !showGroups;
    document.getElementById('btn-groups').style.color = showGroups ? 'var(--green)' : 'var(--muted)';
  };

  window.toggleLabels = function() {
    showLabels = !showLabels;
    document.getElementById('btn-labels').style.color = showLabels ? 'var(--green)' : 'var(--muted)';
  };

  // --- Build legend ---
  function buildLegend() {
    const el = document.getElementById('map-legend');
    let html = '<h4>Legenda</h4>';

    if (groups.length) {
      html += '<div class="legend-section"><div class="legend-title">Skupiny</div>';
      groups.forEach(g => {
        html += `<div class="legend-item" onclick="filterGroup(${g.id})">
          <span class="legend-rect" style="background:${g.color}15;border-color:${g.color}"></span>${g.name}</div>`;
      });
      html += '</div>';
    }

    if (tags.length) {
      html += '<div class="legend-section"><div class="legend-title">Štítky</div>';
      tags.forEach(t => {
        html += `<div class="legend-item" onclick="filterTag(${t.id})">
          <span class="legend-dot" style="background:${t.color}"></span>${t.name}</div>`;
      });
      html += '</div>';
    }

    // Relationship types in use
    const usedTypes = new Set(edges.map(e => e.type));
    if (usedTypes.size) {
      html += '<div class="legend-section"><div class="legend-title">Vztahy</div>';
      usedTypes.forEach(t => {
        html += `<div class="legend-item"><span class="legend-dot" style="background:${REL_COLORS[t]||'#607d8b'}"></span>${REL_LABELS[t]||t}</div>`;
      });
      html += '</div>';
    }

    el.innerHTML = html;
  }

  // --- Build filter chips ---
  function buildFilters() {
    const el = document.getElementById('map-filters');
    let html = '<button class="filter-chip active" onclick="clearFilter()">Vše</button>';
    groups.forEach(g => {
      html += `<button class="filter-chip" onclick="filterGroup(${g.id})" data-filter="g${g.id}" style="border-left: 3px solid ${g.color}">${g.name}</button>`;
    });
    tags.forEach(t => {
      html += `<button class="filter-chip" onclick="filterTag(${t.id})" data-filter="t${t.id}">${t.icon||''} ${t.name}</button>`;
    });
    el.innerHTML = html;
  }

  window.filterGroup = function(gid) {
    setActiveChip('g' + gid);
    nodes.forEach(n => {
      n.visible = n.group_ids && n.group_ids.includes(gid);
    });
    // Also show connected nodes
    edges.forEach(e => {
      if (e.a.visible) e.b.visible = true;
      if (e.b.visible) e.a.visible = true;
    });
  };

  window.filterTag = function(tid) {
    setActiveChip('t' + tid);
    nodes.forEach(n => {
      n.visible = n.tag_ids && n.tag_ids.includes(tid);
    });
    edges.forEach(e => {
      if (e.a.visible) e.b.visible = true;
      if (e.b.visible) e.a.visible = true;
    });
  };

  window.clearFilter = function() {
    setActiveChip(null);
    nodes.forEach(n => n.visible = true);
  };

  function setActiveChip(id) {
    document.querySelectorAll('.filter-chip').forEach(c => c.classList.remove('active'));
    if (id) {
      const chip = document.querySelector(`[data-filter="${id}"]`);
      if (chip) chip.classList.add('active');
    } else {
      document.querySelector('.filter-chip').classList.add('active');
    }
  }

  // --- Init ---
  resize();
  window.addEventListener('resize', resize);
  loadData();

})();
