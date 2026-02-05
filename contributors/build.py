#!/usr/bin/env python3
"""Build standalone HTML with embedded JSON data.

Run from repository root:
    .venv/bin/python contributors/build.py

This generates index.html with episodes.json embedded directly,
so it works without a web server (no CORS issues).
"""

import json
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
EPISODES_FILE = os.path.join(SCRIPT_DIR, "episodes.json")
OUTPUT_FILE = os.path.join(SCRIPT_DIR, "index.html")

HTML_TEMPLATE = '''<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Radio-T Contributors</title>
    <style>
        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
            background: #0d1117;
            color: #c9d1d9;
            line-height: 1.5;
            padding: 20px;
        }

        .container {
            max-width: 1200px;
            margin: 0 auto;
        }

        h1 {
            font-size: 24px;
            font-weight: 600;
            margin-bottom: 8px;
            color: #f0f6fc;
        }

        .subtitle {
            color: #8b949e;
            margin-bottom: 24px;
            font-size: 14px;
        }

        .controls {
            display: flex;
            gap: 16px;
            margin-bottom: 24px;
            flex-wrap: wrap;
            align-items: center;
        }

        .control-group {
            display: flex;
            align-items: center;
            gap: 8px;
        }

        label {
            font-size: 14px;
            color: #8b949e;
        }

        select, input {
            background: #21262d;
            border: 1px solid #30363d;
            border-radius: 6px;
            color: #c9d1d9;
            padding: 5px 12px;
            font-size: 14px;
        }

        select:focus, input:focus {
            outline: none;
            border-color: #58a6ff;
            box-shadow: 0 0 0 3px rgba(88, 166, 255, 0.3);
        }

        #contributors-list {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 16px;
        }

        @media (max-width: 900px) {
            #contributors-list {
                grid-template-columns: 1fr;
            }
        }

        .contributor-card {
            background: #161b22;
            border: 1px solid #30363d;
            border-radius: 6px;
            overflow: hidden;
        }

        .contributor-header {
            display: flex;
            align-items: center;
            padding: 16px;
            border-bottom: 1px solid #21262d;
            gap: 12px;
        }

        .avatar {
            width: 48px;
            height: 48px;
            border-radius: 50%;
            background: linear-gradient(135deg, #238636, #2ea043);
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 600;
            font-size: 18px;
            color: white;
            flex-shrink: 0;
        }

        .contributor-info {
            flex: 1;
        }

        .contributor-name {
            font-size: 16px;
            font-weight: 600;
            color: #f0f6fc;
        }

        .contributor-stats {
            font-size: 13px;
            color: #8b949e;
        }

        .chart-container {
            padding: 16px;
            height: 100px;
            position: relative;
        }

        .chart {
            display: flex;
            align-items: flex-end;
            height: 100%;
            gap: 1px;
            position: relative;
        }

        .bar-group {
            flex: 1;
            display: flex;
            flex-direction: column;
            align-items: center;
            height: 100%;
            justify-content: flex-end;
            min-width: 2px;
            position: relative;
        }

        .bar {
            width: 100%;
            background: #238636;
            border-radius: 2px 2px 0 0;
            min-height: 2px;
            transition: background 0.2s;
        }

        .bar:hover {
            background: #3fb950;
        }

        .bar-group:hover .tooltip {
            display: block;
        }

        .tooltip {
            display: none;
            position: absolute;
            bottom: calc(100% + 8px);
            left: 50%;
            transform: translateX(-50%);
            background: #1f2428;
            border: 1px solid #30363d;
            border-radius: 6px;
            padding: 8px 12px;
            font-size: 12px;
            white-space: nowrap;
            z-index: 100;
            box-shadow: 0 8px 24px rgba(0,0,0,0.5);
        }

        .tooltip::after {
            content: '';
            position: absolute;
            top: 100%;
            left: 50%;
            transform: translateX(-50%);
            border: 6px solid transparent;
            border-top-color: #30363d;
        }

        .year-labels {
            display: flex;
            justify-content: space-between;
            padding: 8px 16px 0;
            font-size: 11px;
            color: #8b949e;
        }

        .summary {
            background: #161b22;
            border: 1px solid #30363d;
            border-radius: 6px;
            padding: 20px;
            margin-bottom: 24px;
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 20px;
        }

        .summary-item {
            text-align: center;
        }

        .summary-value {
            font-size: 28px;
            font-weight: 600;
            color: #58a6ff;
        }

        .summary-label {
            font-size: 12px;
            color: #8b949e;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }

        .host-badge {
            background: #238636;
            color: white;
            font-size: 11px;
            padding: 2px 8px;
            border-radius: 10px;
            margin-left: 8px;
        }

        .guest-badge {
            background: #1f6feb;
            color: white;
            font-size: 11px;
            padding: 2px 8px;
            border-radius: 10px;
            margin-left: 8px;
        }

        .caller-badge {
            background: #9333ea;
            color: white;
            font-size: 11px;
            padding: 2px 8px;
            border-radius: 10px;
            margin-left: 8px;
        }

        .former-host-badge {
            background: #6b7280;
            color: white;
            font-size: 11px;
            padding: 2px 8px;
            border-radius: 10px;
            margin-left: 8px;
        }

        .search-input {
            width: 200px;
        }

        @media (max-width: 600px) {
            .controls {
                flex-direction: column;
                align-items: flex-start;
            }
            .search-input {
                width: 100%;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>📻 Radio-T Contributors</h1>
        <p class="subtitle">Участники подкаста по времени в эфире</p>

        <div id="content">
            <div class="summary">
                <div class="summary-item">
                    <div class="summary-value" id="total-episodes">-</div>
                    <div class="summary-label">Выпусков</div>
                </div>
                <div class="summary-item">
                    <div class="summary-value" id="active-hosts">-</div>
                    <div class="summary-label">Ведущих</div>
                </div>
                <div class="summary-item">
                    <div class="summary-value" id="former-hosts">-</div>
                    <div class="summary-label">Бывших ведущих</div>
                </div>
                <div class="summary-item">
                    <div class="summary-value" id="total-guests">-</div>
                    <div class="summary-label">Гостей</div>
                </div>
                <div class="summary-item">
                    <div class="summary-value" id="total-hours">-</div>
                    <div class="summary-label">Часов эфира</div>
                </div>
                <div class="summary-item">
                    <div class="summary-value" id="date-range">-</div>
                    <div class="summary-label">Период</div>
                </div>
            </div>

            <div class="controls">
                <div class="control-group">
                    <label for="metric">Метрика:</label>
                    <select id="metric">
                        <option value="time">Время в эфире</option>
                        <option value="episodes">Число выпусков</option>
                    </select>
                </div>
                <div class="control-group">
                    <label for="sort">Сортировка:</label>
                    <select id="sort">
                        <option value="time">По времени в эфире</option>
                        <option value="episodes">По числу выпусков</option>
                        <option value="name">По имени</option>
                        <option value="recent">По последнему участию</option>
                    </select>
                </div>
                <div class="control-group">
                    <label for="filter">Показать:</label>
                    <select id="filter">
                        <option value="all">Всех</option>
                        <option value="hosts">Ведущих</option>
                        <option value="guests">Гостей</option>
                        <option value="callers">Звонящих</option>
                    </select>
                </div>
                <div class="control-group">
                    <label for="minEpisodes">Мин. выпусков:</label>
                    <select id="minEpisodes">
                        <option value="1">1+</option>
                        <option value="5">5+</option>
                        <option value="10" selected>10+</option>
                        <option value="50">50+</option>
                        <option value="100">100+</option>
                    </select>
                </div>
                <div class="control-group">
                    <label for="search">Поиск:</label>
                    <input type="text" id="search" class="search-input" placeholder="Имя участника...">
                </div>
            </div>

            <div id="contributors-list"></div>
        </div>
    </div>

    <script>
        const HOST_COLORS = {
            'Umputun': '#e74c3c',
            'Bobuk': '#3498db',
            'Gray': '#9b59b6',
            'Ksenks': '#e91e63',
            'Alek.sys': '#2ecc71',
            'Marin_k_a': '#f39c12'
        };

        // Embedded data
        const episodesData = __EPISODES_DATA__;

        let contributorsData = {};

        function processData() {
            contributorsData = {};

            episodesData.forEach(ep => {
                const date = ep.date;
                const month = date ? date.substring(0, 7) : null;

                ep.contributors.forEach(c => {
                    if (!contributorsData[c.name]) {
                        contributorsData[c.name] = {
                            name: c.name,
                            type: c.type,  // host, guest, caller
                            female: c.female || false,
                            former: c.former || false,
                            totalSeconds: 0,
                            episodes: 0,
                            firstEpisode: ep.episode,
                            lastEpisode: ep.episode,
                            firstDate: date,
                            lastDate: date,
                            byMonth: {},
                            episodesByMonth: {}
                        };
                    }

                    const contrib = contributorsData[c.name];
                    contrib.totalSeconds += c.seconds;
                    contrib.episodes++;
                    contrib.lastEpisode = ep.episode;
                    contrib.lastDate = date;

                    if (date) {
                        // Aggregate by quarter: 2006-Q1, 2006-Q2, etc.
                        const year = date.substring(0, 4);
                        const month = parseInt(date.substring(5, 7));
                        const quarter = Math.ceil(month / 3);
                        const qKey = `${year}-Q${quarter}`;

                        if (!contrib.byMonth[qKey]) {
                            contrib.byMonth[qKey] = 0;
                            contrib.episodesByMonth[qKey] = 0;
                        }
                        contrib.byMonth[qKey] += c.seconds;
                        contrib.episodesByMonth[qKey] += 1;
                    }
                });
            });
        }

        function formatTime(seconds) {
            const hours = Math.floor(seconds / 3600);
            const minutes = Math.floor((seconds % 3600) / 60);
            if (hours > 0) {
                return `${hours}ч ${minutes}м`;
            }
            return `${minutes}м`;
        }

        function getInitials(name) {
            return name.substring(0, 2).toUpperCase();
        }

        function getContributorColor(name) {
            if (HOST_COLORS[name]) return HOST_COLORS[name];
            let hash = 0;
            for (let i = 0; i < name.length; i++) {
                hash = name.charCodeAt(i) + ((hash << 5) - hash);
            }
            const hue = hash % 360;
            return `hsl(${hue}, 50%, 45%)`;
        }

        function getAllQuarters() {
            // Generate all quarters from first to last episode
            const quarters = [];
            const years = new Set();
            episodesData.forEach(ep => {
                if (ep.date) {
                    years.add(ep.date.substring(0, 4));
                }
            });
            const sortedYears = Array.from(years).sort();
            const firstYear = parseInt(sortedYears[0]);
            const lastYear = parseInt(sortedYears[sortedYears.length - 1]);

            for (let y = firstYear; y <= lastYear; y++) {
                for (let q = 1; q <= 4; q++) {
                    quarters.push(`${y}-Q${q}`);
                }
            }
            return quarters;
        }

        function getYears() {
            const years = new Set();
            episodesData.forEach(ep => {
                if (ep.date) {
                    years.add(ep.date.substring(0, 4));
                }
            });
            return Array.from(years).sort();
        }

        function renderContributor(contrib, allQuarters, metric) {
            const card = document.createElement('div');
            card.className = 'contributor-card';

            const color = getContributorColor(contrib.name);
            let badge;
            if (contrib.type === 'host') {
                if (contrib.former) {
                    badge = contrib.female
                        ? '<span class="former-host-badge">Бывшая ведущая</span>'
                        : '<span class="former-host-badge">Бывший ведущий</span>';
                } else {
                    badge = contrib.female
                        ? '<span class="host-badge">Ведущая</span>'
                        : '<span class="host-badge">Ведущий</span>';
                }
            } else if (contrib.type === 'caller') {
                badge = '<span class="caller-badge">Звонящий</span>';
            } else {
                badge = '<span class="guest-badge">Гость</span>';
            }

            const dataByQuarter = metric === 'episodes' ? contrib.episodesByMonth : contrib.byMonth;
            const maxValue = Math.max(...Object.values(dataByQuarter), 1);

            let barsHtml = '';
            allQuarters.forEach(quarter => {
                const value = dataByQuarter[quarter] || 0;
                const height = value > 0 ? Math.max(2, (value / maxValue) * 80) : 0;

                let tooltipText;
                if (metric === 'episodes') {
                    tooltipText = value > 0 ? `${quarter}<br>${value} выпуск${value === 1 ? '' : value < 5 ? 'а' : 'ов'}` : '';
                } else {
                    tooltipText = value > 0 ? `${quarter}<br>${formatTime(value)}` : '';
                }

                const tooltip = value > 0 ? `<div class="tooltip">${tooltipText}</div>` : '';
                barsHtml += `
                    <div class="bar-group">
                        <div class="bar" style="height: ${height}px; background: ${value > 0 ? color : 'transparent'}"></div>
                        ${tooltip}
                    </div>
                `;
            });

            // Year labels with gaps (show every 2-3 years for readability)
            const years = getYears();
            const yearsHtml = years.map((y, i) => {
                // Show every 2nd year, or first/last
                if (i === 0 || i === years.length - 1 || i % 2 === 0) {
                    return `<span>${y}</span>`;
                }
                return '<span></span>';
            }).join('');

            card.innerHTML = `
                <div class="contributor-header">
                    <div class="avatar" style="background: ${color}">${getInitials(contrib.name)}</div>
                    <div class="contributor-info">
                        <div class="contributor-name">${contrib.name}${badge}</div>
                        <div class="contributor-stats">
                            ${formatTime(contrib.totalSeconds)} за ${contrib.episodes} выпусков
                            · ep${contrib.firstEpisode}–${contrib.lastEpisode}
                        </div>
                    </div>
                </div>
                <div class="chart-container">
                    <div class="chart">${barsHtml}</div>
                </div>
                <div class="year-labels">${yearsHtml}</div>
            `;

            return card;
        }

        function render() {
            const metric = document.getElementById('metric').value;
            const sortBy = document.getElementById('sort').value;
            const filter = document.getElementById('filter').value;
            const minEpisodes = parseInt(document.getElementById('minEpisodes').value);
            const search = document.getElementById('search').value.toLowerCase();

            let contributors = Object.values(contributorsData);

            if (filter === 'hosts') {
                contributors = contributors.filter(c => c.type === 'host');
            } else if (filter === 'guests') {
                contributors = contributors.filter(c => c.type === 'guest');
            } else if (filter === 'callers') {
                contributors = contributors.filter(c => c.type === 'caller');
            }

            contributors = contributors.filter(c => c.episodes >= minEpisodes);

            if (search) {
                contributors = contributors.filter(c => c.name.toLowerCase().includes(search));
            }

            switch (sortBy) {
                case 'time':
                    contributors.sort((a, b) => b.totalSeconds - a.totalSeconds);
                    break;
                case 'episodes':
                    contributors.sort((a, b) => b.episodes - a.episodes);
                    break;
                case 'name':
                    contributors.sort((a, b) => a.name.localeCompare(b.name));
                    break;
                case 'recent':
                    contributors.sort((a, b) => b.lastEpisode - a.lastEpisode);
                    break;
            }

            const allQuarters = getAllQuarters();
            const container = document.getElementById('contributors-list');
            container.innerHTML = '';

            contributors.forEach(contrib => {
                container.appendChild(renderContributor(contrib, allQuarters, metric));
            });

            const allContribs = Object.values(contributorsData);
            const totalHours = allContribs.reduce((sum, c) => sum + c.totalSeconds, 0) / 3600;
            const years = getYears();

            // Count active hosts (appeared in last year) and former hosts
            const lastYear = parseInt(years[years.length - 1]);
            const oneYearAgo = `${lastYear - 1}`;
            const allHosts = allContribs.filter(c => c.type === 'host');
            const activeHosts = allHosts.filter(c => c.lastDate && c.lastDate >= oneYearAgo).length;
            const formerHosts = allHosts.length - activeHosts;

            const totalGuests = allContribs.filter(c => c.type === 'guest').length;

            document.getElementById('total-episodes').textContent = episodesData.length;
            document.getElementById('active-hosts').textContent = activeHosts;
            document.getElementById('former-hosts').textContent = formerHosts;
            document.getElementById('total-guests').textContent = totalGuests;
            document.getElementById('total-hours').textContent = Math.round(totalHours);
            document.getElementById('date-range').textContent = `${years[0]}–${years[years.length - 1]}`;
        }

        document.getElementById('metric').addEventListener('change', render);
        document.getElementById('sort').addEventListener('change', render);
        document.getElementById('filter').addEventListener('change', render);
        document.getElementById('minEpisodes').addEventListener('change', render);
        document.getElementById('search').addEventListener('input', render);

        // Initialize
        processData();
        render();
    </script>
</body>
</html>
'''


def main():
    # Read episodes data
    with open(EPISODES_FILE) as f:
        episodes_data = json.load(f)

    # Embed data into HTML
    json_data = json.dumps(episodes_data, ensure_ascii=False)
    html = HTML_TEMPLATE.replace('__EPISODES_DATA__', json_data)

    # Write output
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"Built {OUTPUT_FILE}")
    print(f"Size: {len(html) / 1024:.0f} KB")
    print(f"Episodes: {len(episodes_data)}")


if __name__ == "__main__":
    main()
