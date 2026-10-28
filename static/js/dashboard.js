/*
 * HomeValue — Prediction Dashboard
 *
 * Renders the dashboard's charts as inline SVG from real data supplied by
 * /api/dashboard/summary. No charting library is used, so the visuals work
 * offline, stay crisp at any zoom, and honour the site's design tokens.
 *
 * Every value drawn here comes from logged predictions or from the saved model
 * metrics. Nothing is simulated or placeholder data.
 */
(function () {
  'use strict';

  var SVG_NS = 'http://www.w3.org/2000/svg';

  var C = {
    primary: '#1B4D3E',
    primaryMid: '#2E7762',
    primarySoft: '#DCECE6',
    accent: '#A85A2C',
    accentSoft: '#F6ECE6',
    slate: '#8C9BA5',
    grid: '#EAE7E1',
    axis: '#D5D2C9',
    text: '#1F2933',
    muted: '#6B7A88',
    surface: '#FFFFFF'
  };

  /* ------------------------------------------------------------------ */
  /* Small helpers                                                       */
  /* ------------------------------------------------------------------ */
  function el(tag, attrs, text) {
    var node = document.createElementNS(SVG_NS, tag);
    if (attrs) {
      for (var key in attrs) {
        if (Object.prototype.hasOwnProperty.call(attrs, key)) {
          node.setAttribute(key, attrs[key]);
        }
      }
    }
    if (text !== undefined && text !== null) {
      node.textContent = text;
    }
    return node;
  }

  function money(value) {
    if (value === null || value === undefined || isNaN(value)) return '—';
    return '$' + Math.round(value).toLocaleString('en-US');
  }

  function moneyShort(value) {
    if (value === null || value === undefined || isNaN(value)) return '—';
    var abs = Math.abs(value);
    if (abs >= 1000000) return '$' + (value / 1000000).toFixed(1) + 'M';
    if (abs >= 1000) return '$' + Math.round(value / 1000) + 'k';
    return '$' + Math.round(value);
  }

  function num(value, dp) {
    if (value === null || value === undefined || isNaN(value)) return '—';
    return Number(value).toLocaleString('en-US', {
      minimumFractionDigits: dp || 0,
      maximumFractionDigits: dp || 0
    });
  }

  function bucketLabel(d) {
    if (d.bucket === 'hour') return d.date.slice(11) + 'h';
    return d.date.slice(5);
  }

  function svgRoot(width, height) {
    var svg = el('svg', {
      viewBox: '0 0 ' + width + ' ' + height,
      preserveAspectRatio: 'xMidYMid meet',
      role: 'img',
      width: '100%',
      height: height
    });
    return svg;
  }

  function emptyMessage(container, message) {
    var div = document.createElement('div');
    div.className = 'chart-empty';
    div.textContent = message;
    container.innerHTML = '';
    container.appendChild(div);
  }

  function mount(container, svg) {
    container.innerHTML = '';
    container.appendChild(svg);
  }

  function niceMax(value) {
    if (!value || value <= 0) return 1;
    var mag = Math.pow(10, Math.floor(Math.log10(value)));
    return Math.ceil(value / mag) * mag;
  }

  /* ------------------------------------------------------------------ */
  /* 1. Timeline: bars = estimates per day, line = median estimate       */
  /* ------------------------------------------------------------------ */
  function chartTimeline(container, data) {
    if (!data || !data.length) {
      emptyMessage(container, 'No dated activity yet.');
      return;
    }

    var W = 560, H = 250;
    var m = { top: 18, right: 52, bottom: 42, left: 44 };
    var iw = W - m.left - m.right;
    var ih = H - m.top - m.bottom;

    var svg = svgRoot(W, H);
    var counts = data.map(function (d) { return d.count; });
    var meds = data.map(function (d) { return d.median; });
    var maxCount = Math.max.apply(null, counts.concat([1]));
    var maxMed = Math.max.apply(null, meds.concat([1]));
    var minMed = Math.min.apply(null, meds);
    // Every logged median is identical (a single bucket). Do not invent an
    // axis range around it -- pin the marker mid-height and label just it.
    var flatMed = maxMed === minMed;
    var medSpan = flatMed ? 0 : (maxMed - minMed);

    var band = iw / data.length;
    var barW = Math.max(6, Math.min(38, band * 0.5));

    // horizontal gridlines
    for (var g = 0; g <= 4; g++) {
      var y = m.top + (ih / 4) * g;
      svg.appendChild(el('line', {
        x1: m.left, y1: y, x2: m.left + iw, y2: y,
        stroke: C.grid, 'stroke-width': 1
      }));
      svg.appendChild(el('text', {
        x: m.left - 8, y: y + 3.5, 'text-anchor': 'end',
        'font-size': 10, fill: C.muted
      }, num(maxCount - (maxCount / 4) * g)));
    }

    // bars (count)
    data.forEach(function (d, i) {
      var cx = m.left + band * i + band / 2;
      var h = (d.count / maxCount) * ih;
      var bar = el('rect', {
        x: cx - barW / 2, y: m.top + ih - h, width: barW, height: Math.max(h, 1),
        fill: C.primary, rx: 3, opacity: 0.82
      });
      bar.appendChild(el('title', null,
        d.date + ': ' + d.count + ' estimate(s), median ' + money(d.median)));
      svg.appendChild(bar);

      if (i % Math.ceil(data.length / 6) === 0 || data.length === 1) {
        svg.appendChild(el('text', {
          x: cx, y: m.top + ih + 16, 'text-anchor': 'middle',
          'font-size': 9.5, fill: C.muted
        }, bucketLabel(d)));
      }
    });

    // median price line (secondary axis)
    var pts = data.map(function (d, i) {
      var cx = m.left + band * i + band / 2;
      var cy = flatMed
        ? m.top + ih / 2
        : m.top + ih - ((d.median - minMed) / medSpan) * ih * 0.82 - ih * 0.09;
      return [cx, cy];
    });

    if (pts.length > 1) {
      var dPath = pts.map(function (p, i) {
        return (i === 0 ? 'M' : 'L') + p[0].toFixed(1) + ' ' + p[1].toFixed(1);
      }).join(' ');
      svg.appendChild(el('path', {
        d: dPath, fill: 'none', stroke: C.accent,
        'stroke-width': 2, 'stroke-linejoin': 'round', 'stroke-linecap': 'round'
      }));
    }

    pts.forEach(function (p, i) {
      var dot = el('circle', { cx: p[0], cy: p[1], r: 3.4, fill: C.surface, stroke: C.accent, 'stroke-width': 2 });
      dot.appendChild(el('title', null, data[i].date + ': median ' + money(data[i].median)));
      svg.appendChild(dot);
    });

    // right axis labels for the median line
    var fracs = flatMed ? [0.5] : [0, 0.5, 1];
    fracs.forEach(function (frac) {
      var val = flatMed ? maxMed : minMed + medSpan * frac;
      var cy = flatMed
        ? m.top + ih / 2
        : m.top + ih - (frac * ih * 0.82) - ih * 0.09;
      svg.appendChild(el('text', {
        x: m.left + iw + 8, y: cy + 3.5, 'font-size': 9.5, fill: C.accent
      }, moneyShort(val)));
    });

    // legend
    var lg = el('g');
    lg.appendChild(el('rect', { x: m.left, y: H - 16, width: 9, height: 9, fill: C.primary, rx: 2, opacity: 0.82 }));
    lg.appendChild(el('text', { x: m.left + 14, y: H - 8, 'font-size': 10, fill: C.muted }, 'Estimates logged'));
    lg.appendChild(el('line', { x1: m.left + 128, y1: H - 11.5, x2: m.left + 144, y2: H - 11.5, stroke: C.accent, 'stroke-width': 2 }));
    lg.appendChild(el('text', { x: m.left + 150, y: H - 8, 'font-size': 10, fill: C.muted }, 'Median estimate'));
    svg.appendChild(lg);

    svg.appendChild(el('text', {
      x: m.left - 34, y: m.top - 6, 'font-size': 10, fill: C.muted
    }, 'Count'));

    mount(container, svg);
  }

  /* ------------------------------------------------------------------ */
  /* 2. Histogram of estimated prices                                    */
  /* ------------------------------------------------------------------ */
  function chartHistogram(container, data) {
    if (!data || !data.length) {
      emptyMessage(container, 'No estimates to plot yet.');
      return;
    }

    var W = 560, H = 250;
    var m = { top: 18, right: 16, bottom: 46, left: 44 };
    var iw = W - m.left - m.right;
    var ih = H - m.top - m.bottom;

    var svg = svgRoot(W, H);
    var maxCount = Math.max.apply(null, data.map(function (d) { return d.count; }).concat([1]));
    var band = iw / data.length;

    for (var g = 0; g <= 4; g++) {
      var y = m.top + (ih / 4) * g;
      svg.appendChild(el('line', {
        x1: m.left, y1: y, x2: m.left + iw, y2: y,
        stroke: C.grid, 'stroke-width': 1
      }));
      svg.appendChild(el('text', {
        x: m.left - 8, y: y + 3.5, 'text-anchor': 'end',
        'font-size': 10, fill: C.muted
      }, num(maxCount - (maxCount / 4) * g)));
    }

    data.forEach(function (d, i) {
      var h = (d.count / maxCount) * ih;
      var x = m.left + band * i + band * 0.12;
      var w = band * 0.76;
      var bar = el('rect', {
        x: x, y: m.top + ih - h, width: w, height: Math.max(h, d.count ? 1 : 0),
        fill: C.primary, rx: 2.5, opacity: 0.85
      });
      bar.appendChild(el('title', null,
        moneyShort(d.from) + ' – ' + moneyShort(d.to) + ': ' + d.count + ' estimate(s)'));
      svg.appendChild(bar);

      if (d.count) {
        svg.appendChild(el('text', {
          x: x + w / 2, y: m.top + ih - h - 5, 'text-anchor': 'middle',
          'font-size': 9.5, fill: C.muted
        }, d.count));
      }

      if (i % Math.ceil(data.length / 6) === 0) {
        svg.appendChild(el('text', {
          x: x, y: m.top + ih + 16, 'text-anchor': 'middle',
          'font-size': 9.5, fill: C.muted
        }, moneyShort(d.from)));
      }
    });

    svg.appendChild(el('line', {
      x1: m.left, y1: m.top + ih, x2: m.left + iw, y2: m.top + ih,
      stroke: C.axis, 'stroke-width': 1
    }));
    svg.appendChild(el('text', {
      x: m.left + iw / 2, y: H - 8, 'text-anchor': 'middle',
      'font-size': 10, fill: C.muted
    }, 'Estimated price band'));
    svg.appendChild(el('text', {
      x: m.left - 34, y: m.top - 6, 'font-size': 10, fill: C.muted
    }, 'Count'));

    mount(container, svg);
  }

  /* ------------------------------------------------------------------ */
  /* 3 & 4. Horizontal bar rankings                                      */
  /* ------------------------------------------------------------------ */
  function chartRanking(container, data, opts) {
    if (!data || !data.length) {
      emptyMessage(container, 'Nothing to show yet.');
      return;
    }

    var limit = (opts && opts.limit) || 8;
    var rows = data.slice(0, limit);
    var W = 560;
    var rowH = 30;
    var m = { top: 10, right: 76, bottom: 24, left: 128 };
    var H = m.top + m.bottom + rowH * rows.length;
    var iw = W - m.left - m.right;

    var svg = svgRoot(W, H);
    var maxVal = Math.max.apply(null, rows.map(function (d) { return d.median; }).concat([1]));

    rows.forEach(function (d, i) {
      var y = m.top + rowH * i;
      var barH = 15;
      var w = Math.max(2, (d.median / maxVal) * iw);

      svg.appendChild(el('text', {
        x: m.left - 10, y: y + barH / 2 + 4, 'text-anchor': 'end',
        'font-size': 11, fill: C.text
      }, d.name.length > 20 ? d.name.slice(0, 19) + '…' : d.name));

      svg.appendChild(el('rect', {
        x: m.left, y: y, width: iw, height: barH, rx: 3, fill: C.primarySoft
      }));

      var bar = el('rect', {
        x: m.left, y: y, width: w, height: barH, rx: 3,
        fill: (opts && opts.color) || C.primary, opacity: 0.9
      });
      bar.appendChild(el('title', null,
        d.name + ': median ' + money(d.median) + ' across ' + d.count + ' estimate(s)'));
      svg.appendChild(bar);

      svg.appendChild(el('text', {
        x: m.left + iw + 8, y: y + barH / 2 + 4,
        'font-size': 10.5, fill: C.text, 'font-weight': 600
      }, moneyShort(d.median)));

      svg.appendChild(el('text', {
        x: m.left + w + 6, y: y + barH / 2 + 4,
        'font-size': 9.5, fill: C.muted
      }, w > iw * 0.55 ? d.count + '×' : ''));
    });

    mount(container, svg);
  }

  /* ------------------------------------------------------------------ */
  /* 5. Scatter: living area vs estimated price                          */
  /* ------------------------------------------------------------------ */
  function chartScatter(container, data) {
    if (!data || !data.length) {
      emptyMessage(container, 'No estimates to plot yet.');
      return;
    }

    var W = 560, H = 300;
    var m = { top: 18, right: 18, bottom: 44, left: 58 };
    var iw = W - m.left - m.right;
    var ih = H - m.top - m.bottom;

    var svg = svgRoot(W, H);
    var areas = data.map(function (d) { return d.area; });
    var prices = data.map(function (d) { return d.price; });
    var ages = data.map(function (d) { return d.age; }).filter(function (a) { return a !== null && !isNaN(a); });

    var minA = Math.min.apply(null, areas), maxA = Math.max.apply(null, areas);
    var minP = Math.min.apply(null, prices), maxP = Math.max.apply(null, prices);
    var maxAge = ages.length ? Math.max.apply(null, ages) : 1;

    var padA = (maxA - minA) * 0.06 || 100;
    var padP = (maxP - minP) * 0.08 || 1000;
    var a0 = minA - padA, a1 = maxA + padA;
    var p0 = Math.max(0, minP - padP), p1 = maxP + padP;

    function xOf(v) { return m.left + ((v - a0) / (a1 - a0)) * iw; }
    function yOf(v) { return m.top + ih - ((v - p0) / (p1 - p0)) * ih; }

    // grid + axes
    for (var g = 0; g <= 4; g++) {
      var y = m.top + (ih / 4) * g;
      svg.appendChild(el('line', { x1: m.left, y1: y, x2: m.left + iw, y2: y, stroke: C.grid, 'stroke-width': 1 }));
      svg.appendChild(el('text', {
        x: m.left - 8, y: y + 3.5, 'text-anchor': 'end', 'font-size': 10, fill: C.muted
      }, moneyShort(p1 - ((p1 - p0) / 4) * g)));
    }
    for (var gx = 0; gx <= 4; gx++) {
      var x = m.left + (iw / 4) * gx;
      svg.appendChild(el('line', { x1: x, y1: m.top, x2: x, y2: m.top + ih, stroke: C.grid, 'stroke-width': 1 }));
      svg.appendChild(el('text', {
        x: x, y: m.top + ih + 16, 'text-anchor': 'middle', 'font-size': 10, fill: C.muted
      }, num(a0 + ((a1 - a0) / 4) * gx)));
    }

    svg.appendChild(el('line', { x1: m.left, y1: m.top + ih, x2: m.left + iw, y2: m.top + ih, stroke: C.axis, 'stroke-width': 1 }));
    svg.appendChild(el('line', { x1: m.left, y1: m.top, x2: m.left, y2: m.top + ih, stroke: C.axis, 'stroke-width': 1 }));

    // points coloured by age
    data.forEach(function (d) {
      var t = (d.age === null || isNaN(d.age)) ? 0 : Math.min(1, d.age / (maxAge || 1));
      var fill = t < 0.5
        ? mix(C.primaryMid, C.primary, t * 2)
        : mix(C.primary, C.accent, (t - 0.5) * 2);

      var dot = el('circle', {
        cx: xOf(d.area), cy: yOf(d.price), r: 4.6,
        fill: fill, 'fill-opacity': 0.78,
        stroke: C.surface, 'stroke-width': 1
      });
      dot.appendChild(el('title', null,
        (d.location || 'Unknown') + ' — ' + num(d.area) + ' sq ft, ' +
        (d.age === null ? 'age n/a' : d.age + ' yrs') + ': ' + money(d.price)));
      svg.appendChild(dot);
    });

    svg.appendChild(el('text', {
      x: m.left + iw / 2, y: H - 8, 'text-anchor': 'middle', 'font-size': 10.5, fill: C.muted
    }, 'Living area (sq ft)'));
    svg.appendChild(el('text', {
      x: 14, y: m.top + ih / 2, 'text-anchor': 'middle', 'font-size': 10.5, fill: C.muted,
      transform: 'rotate(-90 14 ' + (m.top + ih / 2) + ')'
    }, 'Estimated price'));

    // age colour legend
    var lgW = 96, lgX = m.left + iw - lgW, lgY = m.top + 6;
    var gradId = 'ageGrad';
    var defs = el('defs');
    var grad = el('linearGradient', { id: gradId, x1: '0', x2: '1' });
    grad.appendChild(el('stop', { offset: '0%', 'stop-color': C.primaryMid }));
    grad.appendChild(el('stop', { offset: '50%', 'stop-color': C.primary }));
    grad.appendChild(el('stop', { offset: '100%', 'stop-color': C.accent }));
    defs.appendChild(grad);
    svg.appendChild(defs);
    svg.appendChild(el('rect', { x: lgX, y: lgY, width: lgW, height: 7, rx: 3.5, fill: 'url(#' + gradId + ')' }));
    svg.appendChild(el('text', { x: lgX, y: lgY + 19, 'font-size': 9, fill: C.muted }, 'newer'));
    svg.appendChild(el('text', { x: lgX + lgW, y: lgY + 19, 'text-anchor': 'end', 'font-size': 9, fill: C.muted }, 'older'));

    mount(container, svg);
  }

  function mix(hexA, hexB, t) {
    var a = parseInt(hexA.slice(1), 16), b = parseInt(hexB.slice(1), 16);
    var ar = (a >> 16) & 255, ag = (a >> 8) & 255, ab = a & 255;
    var br = (b >> 16) & 255, bg = (b >> 8) & 255, bb = b & 255;
    var r = Math.round(ar + (br - ar) * t);
    var g = Math.round(ag + (bg - ag) * t);
    var bl = Math.round(ab + (bb - ab) * t);
    return 'rgb(' + r + ',' + g + ',' + bl + ')';
  }

  /* ------------------------------------------------------------------ */
  /* 6. Feature importance                                               */
  /* ------------------------------------------------------------------ */
  function chartImportance(container, data) {
    if (!data || !data.length) {
      emptyMessage(container, 'No importance data available.');
      return;
    }

    var W = 560;
    var rowH = 27;
    var m = { top: 8, right: 58, bottom: 8, left: 148 };
    var H = m.top + m.bottom + rowH * data.length;
    var iw = W - m.left - m.right;
    var svg = svgRoot(W, H);

    var maxVal = Math.max.apply(null, data.map(function (d) { return d.importance_pct; }).concat([1]));

    data.forEach(function (d, i) {
      var y = m.top + rowH * i;
      var barH = 12;
      var w = Math.max(2, (d.importance_pct / maxVal) * iw);

      svg.appendChild(el('text', {
        x: m.left - 10, y: y + barH / 2 + 4, 'text-anchor': 'end',
        'font-size': 10.5, fill: C.text
      }, d.label.length > 22 ? d.label.slice(0, 21) + '…' : d.label));

      svg.appendChild(el('rect', {
        x: m.left, y: y, width: iw, height: barH, rx: 3, fill: C.primarySoft
      }));

      var bar = el('rect', {
        x: m.left, y: y, width: w, height: barH, rx: 3, fill: C.primary, opacity: 0.9
      });
      bar.appendChild(el('title', null,
        d.label + ': ' + d.importance_pct + '% impurity importance, ' +
        d.permutation_importance_pct + '% permutation share'));
      svg.appendChild(bar);

      svg.appendChild(el('text', {
        x: m.left + iw + 8, y: y + barH / 2 + 4, 'font-size': 10, fill: C.text, 'font-weight': 600
      }, d.importance_pct.toFixed(1) + '%'));
    });

    mount(container, svg);
  }

  /* ------------------------------------------------------------------ */
  /* 7. Model accuracy                                                   */
  /* ------------------------------------------------------------------ */
  function chartAccuracy(container, metrics, reference) {
    if (!metrics || !metrics.mae) {
      emptyMessage(container, 'No evaluation metrics available.');
      return;
    }

    var rows = [
      { label: 'MAE', value: metrics.mae, money: true, hint: 'Average miss in dollars' },
      { label: 'RMSE', value: metrics.rmse, money: true, hint: 'Large errors weighted more' }
    ];
    if (reference && reference.median) {
      rows.push({
        label: 'MAE as share of median sale',
        value: (metrics.mae / reference.median) * 100,
        pct: true,
        hint: 'Error relative to the dataset median price'
      });
    }

    var W = 560;
    var rowH = 34;
    var m = { top: 8, right: 96, bottom: 8, left: 150 };
    var H = m.top + m.bottom + rowH * rows.length;
    var iw = W - m.left - m.right;

    var svg = svgRoot(W, H);

    // R² band
    var bandY = 0;
    rows.forEach(function (d, i) {
      var y = m.top + rowH * i;
      var barH = 13;
      var scaleMax = d.pct ? Math.max(d.value * 1.6, 30) : Math.max(rows[1].value * 1.15, 1);
      var w = Math.max(2, Math.min(1, d.value / scaleMax) * iw);

      svg.appendChild(el('text', {
        x: m.left - 10, y: y + barH / 2 + 4, 'text-anchor': 'end', 'font-size': 10.5, fill: C.text
      }, d.label.length > 24 ? d.label.slice(0, 23) + '…' : d.label));

      svg.appendChild(el('rect', { x: m.left, y: y, width: iw, height: barH, rx: 3, fill: C.primarySoft }));

      var bar = el('rect', {
        x: m.left, y: y, width: w, height: barH, rx: 3,
        fill: d.pct ? C.accent : C.primary, opacity: 0.9
      });
      bar.appendChild(el('title', null, d.label + ': ' + d.hint));
      svg.appendChild(bar);

      svg.appendChild(el('text', {
        x: m.left + iw + 8, y: y + barH / 2 + 4, 'font-size': 10.5, fill: C.text, 'font-weight': 600
      }, d.money ? money(d.value) : d.value.toFixed(1) + '%'));

      bandY = y + barH;
    });

    mount(container, svg);
  }

  /* ------------------------------------------------------------------ */
  /* Wiring                                                              */
  /* ------------------------------------------------------------------ */
  function renderAll(summary) {
    if (!summary || !summary.has_data) return;

    chartTimeline(document.getElementById('chartTimeline'), summary.timeline);
    chartHistogram(document.getElementById('chartHistogram'), summary.histogram);
    chartRanking(document.getElementById('chartLocation'), summary.by_location, { limit: 8 });
    chartRanking(document.getElementById('chartType'), summary.by_property_type,
                 { limit: 5, color: C.primaryMid });
    chartScatter(document.getElementById('chartScatter'), summary.scatter);
    chartImportance(document.getElementById('chartImportance'), summary.feature_importances);
    chartAccuracy(document.getElementById('chartAccuracy'), summary.model.test_metrics,
                  (summary.dataset_reference || {}).price);
  }

  function showAlert(message) {
    var box = document.getElementById('dashAlert');
    var text = document.getElementById('dashAlertMessage');
    if (!box || !text) return;
    text.textContent = message;
    box.style.display = 'flex';
  }

  function hideAlert() {
    var box = document.getElementById('dashAlert');
    if (box) box.style.display = 'none';
  }

  function post(url, body, onDone) {
    hideAlert();
    return fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: body ? JSON.stringify(body) : '{}'
    })
      .then(function (r) {
        return r.json().catch(function () {
          return { success: false, error: 'The server returned an unreadable response.' };
        });
      })
      .then(function (data) {
        if (!data || !data.success) {
          showAlert((data && data.error) || 'The request could not be completed.');
          return data;
        }
        if (onDone) onDone(data);
        return data;
      })
      .catch(function () {
        showAlert('Could not reach the server. Check that the application is running.');
      });
  }

  function reload() {
    window.location.reload();
  }

  document.addEventListener('DOMContentLoaded', function () {
    var dataNode = document.getElementById('dashData');
    if (dataNode) {
      try {
        window.HOMEVALUE_DASHBOARD = JSON.parse(dataNode.textContent);
      } catch (e) {
        window.HOMEVALUE_DASHBOARD = null;
      }
    }
    renderAll(window.HOMEVALUE_DASHBOARD);

    var refresh = document.getElementById('refreshDash');
    if (refresh) refresh.addEventListener('click', reload);

    var sample = document.getElementById('sampleDash');
    var sampleEmpty = document.getElementById('sampleDashEmpty');

    function runSample(button) {
      if (!button) return;
      button.classList.add('is-busy');
      button.disabled = true;
      post('/api/dashboard/sample', { count: 40 }, function (data) {
        button.classList.remove('is-busy');
        button.disabled = false;
        reload();
      });
    }

    if (sample) sample.addEventListener('click', function () { runSample(sample); });
    if (sampleEmpty) sampleEmpty.addEventListener('click', function () { runSample(sampleEmpty); });

    var clear = document.getElementById('clearDash');
    if (clear) {
      clear.addEventListener('click', function () {
        if (!window.confirm('Delete all logged predictions? This cannot be undone.')) return;
        clear.classList.add('is-busy');
        post('/api/dashboard/clear', null, function () {
          clear.classList.remove('is-busy');
          reload();
        });
      });
    }

    // Re-render on resize so the SVG scales stay tidy
    var t;
    window.addEventListener('resize', function () {
      clearTimeout(t);
      t = setTimeout(function () { renderAll(window.HOMEVALUE_DASHBOARD); }, 220);
    });
  });
})();
