/**
 * EventPulse Analytics & Dashboard Charts
 */

function initRatingDistributionChart(canvasId, ratingData) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) return;

    new Chart(ctx, {
        type: 'bar',
        data: {
            labels: ['1 Star', '2 Stars', '3 Stars', '4 Stars', '5 Stars'],
            datasets: [{
                label: 'Student Responses',
                data: ratingData || [0, 0, 0, 0, 0],
                backgroundColor: [
                    '#B91C1C',
                    '#B45309',
                    '#EAB308',
                    '#0284C7',
                    '#15803D'
                ],
                borderRadius: 6
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: { precision: 0 }
                }
            }
        }
    });
}

function initDepartmentComparisonChart(canvasId, labels, values) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) return;

    new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: labels && labels.length ? labels : ['No Data'],
            datasets: [{
                data: values && values.length ? values : [1],
                backgroundColor: [
                    '#172554',
                    '#C6A76B',
                    '#0284C7',
                    '#15803D',
                    '#B45309',
                    '#9333EA',
                    '#64748B'
                ]
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

function initResponseTrendChart(canvasId, dates, counts) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) return;

    new Chart(ctx, {
        type: 'line',
        data: {
            labels: dates && dates.length ? dates : ['Past 7 Days'],
            datasets: [{
                label: 'Feedback Submissions',
                data: counts && counts.length ? counts : [0],
                borderColor: '#172554',
                backgroundColor: 'rgba(23, 37, 84, 0.08)',
                fill: true,
                tension: 0.35,
                pointBackgroundColor: '#C6A76B',
                pointBorderColor: '#172554',
                pointRadius: 5
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: { precision: 0 }
                }
            }
        }
    });
}
