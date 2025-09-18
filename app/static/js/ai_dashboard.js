document.addEventListener('DOMContentLoaded', function() {
    // Elements
    const runPredictionBtn = document.getElementById('run-prediction');
    const runOptimizationBtn = document.getElementById('run-optimization');
    const runIncidentDetectionBtn = document.getElementById('run-incident-detection');
    const calculateRouteBtn = document.getElementById('calculate-route');
    
    // Event listeners
    runPredictionBtn.addEventListener('click', runTrafficPrediction);
    runOptimizationBtn.addEventListener('click', runSignalOptimization);
    runIncidentDetectionBtn.addEventListener('click', runIncidentDetection);
    calculateRouteBtn.addEventListener('click', calculateOptimalRoute);
    
    function runTrafficPrediction() {
        runPredictionBtn.disabled = true;
        runPredictionBtn.textContent = 'Predicting...';
        
        fetch('/ai/api/ai/predict/traffic', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                location_id: 'current_location',
                steps: 4
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                displayPredictionResults(data);
            } else {
                showNotification('Prediction failed: ' + data.error, 'error');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            showNotification('Error running prediction', 'error');
        })
        .finally(() => {
            runPredictionBtn.disabled = false;
            runPredictionBtn.textContent = 'Predict Next Hour';
        });
    }
    
    function runSignalOptimization() {
        const intersectionId = document.getElementById('intersection-select').value;
        runOptimizationBtn.disabled = true;
        runOptimizationBtn.textContent = 'Optimizing...';
        
        fetch('/ai/api/ai/optimize/signals', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                intersection_id: intersectionId
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                displayOptimizationResults(data);
            } else {
                showNotification('Optimization failed: ' + data.message, 'error');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            showNotification('Error running optimization', 'error');
        })
        .finally(() => {
            runOptimizationBtn.disabled = false;
            runOptimizationBtn.textContent = 'Optimize Signals';
        });
    }
    
    function runIncidentDetection() {
        runIncidentDetectionBtn.disabled = true;
        runIncidentDetectionBtn.textContent = 'Detecting...';
        
        fetch('/ai/api/ai/detect/incidents', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({})
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                displayIncidentResults(data);
            } else {
                showNotification('Incident detection failed: ' + data.error, 'error');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            showNotification('Error detecting incidents', 'error');
        })
        .finally(() => {
            runIncidentDetectionBtn.disabled = false;
            runIncidentDetectionBtn.textContent = 'Detect Incidents';
        });
    }
    
    function calculateOptimalRoute() {
        const origin = document.getElementById('origin-input').value;
        const destination = document.getElementById('destination-input').value;
        
        if (!origin || !destination) {
            showNotification('Please enter both origin and destination', 'error');
            return;
        }
        
        calculateRouteBtn.disabled = true;
        calculateRouteBtn.textContent = 'Calculating...';
        
        fetch('/ai/api/ai/recommend/routes', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                origin: origin,
                destination: destination,
                vehicle_type: 'passenger'
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                displayRouteResults(data);
            } else {
                showNotification('Route calculation failed: ' + data.error, 'error');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            showNotification('Error calculating route', 'error');
        })
        .finally(() => {
            calculateRouteBtn.disabled = false;
            calculateRouteBtn.textContent = 'Calculate Optimal Route';
        });
    }
    
    function displayPredictionResults(data) {
        const container = document.getElementById('prediction-results');
        const predictions = data.predictions;
        const current = data.current_conditions;
        
        let html = `
            <div class="mb-2">
                <strong>Current Conditions:</strong>
                ${current.vehicle_count} vehicles, 
                Avg speed: ${current.avg_speed.toFixed(1)} km/h,
                Congestion: ${getCongestionLabel(current.congestion_level)}
            </div>
            <div>
                <strong>Predictions:</strong>
                <ul class="list-group">
        `;
        
        predictions.forEach(pred => {
            html += `
                <li class="list-group-item d-flex justify-content-between align-items-center">
                    ${new Date(pred.timestamp).toLocaleTimeString()}
                    <span class="badge ${getCongestionBadgeClass(pred.predicted_congestion)} rounded-pill">
                        ${getCongestionLabel(pred.predicted_congestion)}
                    </span>
                </li>
            `;
        });
        
        html += `</ul></div>`;
        container.innerHTML = html;
    }
    
    function displayOptimizationResults(data) {
        const container = document.getElementById('optimization-results');
        const optimization = data.optimization;
        
        let html = `<div class="alert alert-success">Optimization applied successfully!</div>`;
        
        if (optimization.optimized_signals) {
            html += `<ul class="list-group">`;
            for (const [tl_id, settings] of Object.entries(optimization.optimized_signals)) {
                html += `
                    <li class="list-group-item">
                        <strong>${tl_id}:</strong> 
                        State: ${settings.state}, 
                        Duration: ${settings.duration}s
                    </li>
                `;
            }
            html += `</ul>`;
        }
        
        container.innerHTML = html;
    }
    
    function displayIncidentResults(data) {
        const container = document.getElementById('incident-results');
        const incidents = data.incidents;
        
        if (incidents.length === 0) {
            container.innerHTML = `
                <div class="alert alert-success">
                    No incidents detected
                </div>
            `;
            return;
        }
        
        let html = `
            <div class="alert alert-warning">
                ${incidents.length} incident(s) detected
            </div>
            <ul class="list-group">
        `;
        
        incidents.forEach(incident => {
            html += `
                <li class="list-group-item">
                    <strong>${incident.type}</strong> at ${formatPosition(incident.location)}<br>
                    Vehicle: ${incident.vehicle_id}, 
                    Probability: ${(incident.probability * 100).toFixed(1)}%
                </li>
            `;
        });
        
        html += `</ul>`;
        container.innerHTML = html;
    }
    
    function displayRouteResults(data) {
        const container = document.getElementById('route-results');
        const route = data.route;
        
        let html = `
            <div class="alert alert-info">
                Optimal route found
            </div>
            <div>
                <strong>Path:</strong> ${route.path.join(' → ')}<br>
                <strong>Distance:</strong> ${route.distance} km<br>
                <strong>Estimated Time:</strong> ${route.travel_time} minutes<br>
                <strong>Congestion Level:</strong> ${getCongestionLabel(route.congestion_level)}
            </div>
        `;
        
        container.innerHTML = html;
    }
    
    // Helper functions
    function getCongestionLabel(level) {
        if (level >= 2.5) return "High";
        if (level >= 1.5) return "Medium";
        return "Low";
    }
    
    function getCongestionBadgeClass(level) {
        if (level >= 2.5) return "bg-danger";
        if (level >= 1.5) return "bg-warning";
        return "bg-success";
    }
    
    function formatPosition(pos) {
        return `(${pos[0].toFixed(1)}, ${pos[1].toFixed(1)})`;
    }
    
    function showNotification(message, type) {
        // Simple notification implementation
        alert(`${type.toUpperCase()}: ${message}`);
    }
});