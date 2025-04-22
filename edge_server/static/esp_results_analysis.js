// JS for visualizing ESP simulator CSV results
async function fetchAndRenderResults() {
  const resp = await fetch('/esp_results');
  const data = await resp.json();

  // Prepare data for charts
  const times = data.map(row => row.timestamp);
  const loads = data.map(row => parseInt(row.load));
  const results = data.map(row => row.result);
  const responseTimes = data.map(row => parseInt(row.response_time_ms));
  const redirects = data.map(row => row.redirected !== '' ? 1 : 0);

  // Chart.js: Load Distribution
  new Chart(document.getElementById('loadChart'), {
    type: 'line',
    data: {
      labels: times,
      datasets: [{
        label: 'Load Sent',
        data: loads,
        borderColor: 'blue',
        fill: false
      }]
    },
    options: {scales: {x: {display: false}}}
  });

  // Chart.js: Response Time
  new Chart(document.getElementById('respChart'), {
    type: 'line',
    data: {
      labels: times,
      datasets: [{
        label: 'Response Time (ms)',
        data: responseTimes,
        borderColor: 'green',
        fill: false
      }]
    },
    options: {scales: {x: {display: false}}}
  });

  // Chart.js: Success/Failure Pie
  const success = results.filter(x => x === 'success').length;
  const fail = results.filter(x => x === 'fail').length;
  new Chart(document.getElementById('resultChart'), {
    type: 'pie',
    data: {
      labels: ['Success', 'Fail'],
      datasets: [{
        data: [success, fail],
        backgroundColor: ['#4caf50', '#f44336']
      }]
    }
  });

  // Chart.js: Redirections
  new Chart(document.getElementById('redirChart'), {
    type: 'bar',
    data: {
      labels: times,
      datasets: [{
        label: 'Redirections',
        data: redirects,
        backgroundColor: 'orange'
      }]
    },
    options: {scales: {x: {display: false}}}
  });
}
document.addEventListener('DOMContentLoaded', fetchAndRenderResults);
