/**
 * Chart.js Integration for Productivity Analytics
 */
document.addEventListener('DOMContentLoaded', () => {
  const taskChartCanvas = document.getElementById('taskStatusChart');
  const weeklyChartCanvas = document.getElementById('weeklyHoursChart');

  if (!taskChartCanvas && !weeklyChartCanvas) return;

  fetch('/reports/api/chart-data')
    .then(res => res.json())
    .then(data => {
      // 1. Task Status Doughnut Chart
      if (taskChartCanvas && window.Chart) {
        new Chart(taskChartCanvas, {
          type: 'doughnut',
          data: {
            labels: data.taskStatus.labels,
            datasets: [{
              data: data.taskStatus.data,
              backgroundColor: ['#10b981', '#3b82f6', '#f59e0b', '#64748b'],
              borderWidth: 2,
              borderColor: 'transparent'
            }]
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
              legend: { position: 'bottom' }
            }
          }
        });
      }

      // 2. Weekly Working Hours Bar Chart
      if (weeklyChartCanvas && window.Chart) {
        new Chart(weeklyChartCanvas, {
          type: 'bar',
          data: {
            labels: data.weeklyHours.labels,
            datasets: [{
              label: 'Hours Logged',
              data: data.weeklyHours.data,
              backgroundColor: '#3b82f6',
              borderRadius: 8
            }]
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
              y: { beginAtZero: true }
            }
          }
        });
      }
    })
    .catch(err => console.error('Error fetching analytics chart data:', err));
});

