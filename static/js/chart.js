document.addEventListener("DOMContentLoaded", async function() {
    
    // Fetch Data from Python Backend
    const response = await fetch('/api/analytics-data');
    const data = await response.json();

    // 1. Line Chart (Engagement)
    const ctx1 = document.getElementById('engagementChart').getContext('2d');
    
    // Create Gradient for the fill
    let gradient = ctx1.createLinearGradient(0, 0, 0, 400);
    gradient.addColorStop(0, 'rgba(59, 130, 246, 0.5)'); // Blue top
    gradient.addColorStop(1, 'rgba(59, 130, 246, 0)');   // Transparent bottom

    new Chart(ctx1, {
        type: 'line',
        data: {
            labels: ['Day 1', 'Day 2', 'Day 3', 'Day 4', 'Day 5', 'Day 6', 'Day 7'],
            datasets: [{
                label: 'Engagement',
                data: data.engagement_trend,
                borderColor: '#3B82F6', // Bright Blue
                backgroundColor: gradient,
                borderWidth: 2,
                tension: 0.4, // Curved lines
                fill: true,
                pointRadius: 0
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
                y: { grid: { color: '#1F2937' }, ticks: { color: '#9CA3AF' } },
                x: { grid: { display: false }, ticks: { color: '#9CA3AF' } }
            }
        }
    });

    // 2. Bar Chart (Platform Distribution)
    const ctx2 = document.getElementById('platformChart').getContext('2d');
    new Chart(ctx2, {
        type: 'bar',
        data: {
            labels: ['LinkedIn', 'Instagram', 'Facebook'],
            datasets: [{
                data: data.platforms,
                backgroundColor: ['#3B82F6', '#60A5FA', '#93C5FD'],
                borderRadius: 4,
                barThickness: 30
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
                y: { grid: { color: '#1F2937' }, ticks: { color: '#9CA3AF' } },
                x: { grid: { display: false }, ticks: { color: '#9CA3AF' } }
            }
        }
    });
});