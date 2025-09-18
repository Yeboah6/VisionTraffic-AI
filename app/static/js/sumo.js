document.addEventListener('DOMContentLoaded', function() {
    // Elements
    const startBtn = document.getElementById('start-simulation');
    const stopBtn = document.getElementById('stop-simulation');
    const statusBadge = document.getElementById('simulation-status');
    const statsContainer = document.getElementById('simulation-stats');
    const tlForm = document.getElementById('tl-control-form');
    const configSelect = document.getElementById('config-file');
    const aiControlCheckbox = document.getElementById('ai-control');
    const refreshStatsBtn = document.getElementById('refresh-stats');
    const refreshVizBtn = document.getElementById('refresh-visualization');
    const runPredictionBtn = document.getElementById('run-prediction');
    const refreshPerformanceBtn = document.getElementById('refresh-performance');
    
    // Status checking variables
    let simulationStatusCheckInterval = null;
    let lastStatusCheckTime = 0;
    let lastFullStatusCheck = 0;
    let lastStatisticsRefresh = 0;
    let lastVisualizationRefresh = 0;
    const STATUS_CHECK_INTERVAL = 2000;
    const STATS_REFRESH_INTERVAL = 3000;
    const VIZ_REFRESH_INTERVAL = 2000;
    
    // Event listeners
    startBtn.addEventListener('click', startSimulation);
    stopBtn.addEventListener('click', stopSimulation);
    tlForm.addEventListener('submit', controlTrafficLight);
    refreshStatsBtn.addEventListener('click', refreshStatistics);
    refreshVizBtn.addEventListener('click', refreshVisualization);
    runPredictionBtn.addEventListener('click', runTrafficPrediction);
    refreshPerformanceBtn.addEventListener('click', refreshAIPerformance);
    
    // Initialize status checking
    setupStatusChecking();
    
    function setupStatusChecking() {
        // Clear any existing interval
        if (simulationStatusCheckInterval) {
            clearInterval(simulationStatusCheckInterval);
        }
        
        // Set up a new interval with appropriate timing
        simulationStatusCheckInterval = setInterval(() => {
            const currentTime = Date.now();
            if (currentTime - lastStatusCheckTime >= STATUS_CHECK_INTERVAL) {
                checkSimulationStatusLight();
                lastStatusCheckTime = currentTime;
            }
        }, 1000);
    }
    
    function startSimulation() {
        const configFile = configSelect.value;
        const aiControl = aiControlCheckbox.checked;
        
        startBtn.disabled = true;
        startBtn.textContent = 'Starting...';
        
        fetch('/sumo_ai/api/sumo/start', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                config_file: configFile,
                ai_control: aiControl
            })
        })
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            if (data.status === 'success') {
                showNotification('Simulation started successfully', 'success');
                setupStatusChecking();
                checkSimulationStatusLight();
            } else {
                showNotification('Error: ' + data.message, 'error');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            showNotification('Error starting simulation: ' + error.message, 'error');
        })
        .finally(() => {
            startBtn.disabled = false;
            startBtn.textContent = 'Start Simulation';
        });
    }
    
    function stopSimulation() {
        stopBtn.disabled = true;
        stopBtn.textContent = 'Stopping...';
        
        fetch('/sumo_ai/api/sumo/stop', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({})
        })
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            if (data.status === 'success') {
                showNotification('Simulation stopped successfully', 'success');
                // Slow down checks when simulation is not running
                if (simulationStatusCheckInterval) {
                    clearInterval(simulationStatusCheckInterval);
                    simulationStatusCheckInterval = setInterval(checkSimulationStatusLight, 5000);
                }
                checkSimulationStatusLight();
            } else {
                showNotification('Error: ' + data.message, 'error');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            showNotification('Error stopping simulation: ' + error.message, 'error');
        })
        .finally(() => {
            stopBtn.disabled = false;
            stopBtn.textContent = 'Stop Simulation';
        });
    }
    
    let simulationIsRunning = false; // Track simulation status globally

    function checkSimulationStatusLight() {
        if (document.hidden) {
            return;
        }

        // Skip fetch if simulation is not running
        if (!simulationIsRunning) {
            statusBadge.textContent = 'Not Running';
            statusBadge.className = 'badge bg-secondary';
            return;
        }
        
        fetch('/sumo_ai/api/sumo/status/light')
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            simulationIsRunning = (data.status === 'running');
            if (simulationIsRunning) {
                statusBadge.textContent = `Running (${data.vehicle_count} vehicles)`;
                statusBadge.className = 'badge bg-success';
                
                // Only do full update occasionally
                if (Date.now() - lastFullStatusCheck > 5000) {
                    checkSimulationStatusFull();
                    lastFullStatusCheck = Date.now();
                }
            } else {
                statusBadge.textContent = 'Not Running';
                statusBadge.className = 'badge bg-secondary';
            }
        })
        .catch(error => {
            console.error('Error checking light status:', error);
            statusBadge.textContent = 'Connection Error';
            statusBadge.className = 'badge bg-warning';
        });
    }

    // Update simulationIsRunning when starting/stopping simulation
    function startSimulation() {
        const configFile = configSelect.value;
        const aiControl = aiControlCheckbox.checked;
        
        startBtn.disabled = true;
        startBtn.textContent = 'Starting...';
        
        fetch('/sumo_ai/api/sumo/start', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                config_file: configFile,
                ai_control: aiControl
            })
        })
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            if (data.status === 'success') {
                simulationIsRunning = true;
                showNotification('Simulation started successfully', 'success');
                setupStatusChecking();
                checkSimulationStatusLight();
            } else {
                showNotification('Error: ' + data.message, 'error');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            showNotification('Error starting simulation: ' + error.message, 'error');
        })
        .finally(() => {
            startBtn.disabled = false;
            startBtn.textContent = 'Start Simulation';
        });
    }

    function stopSimulation() {
        stopBtn.disabled = true;
        stopBtn.textContent = 'Stopping...';
        
        fetch('/sumo_ai/api/sumo/stop', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({})
        })
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            if (data.status === 'success') {
                simulationIsRunning = false;
                showNotification('Simulation stopped successfully', 'success');
                // Slow down checks when simulation is not running
                if (simulationStatusCheckInterval) {
                    clearInterval(simulationStatusCheckInterval);
                    simulationStatusCheckInterval = setInterval(checkSimulationStatusLight, 5000);
                }
                checkSimulationStatusLight();
            } else {
                showNotification('Error: ' + data.message, 'error');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            showNotification('Error stopping simulation: ' + error.message, 'error');
        })
        .finally(() => {
            stopBtn.disabled = false;
            stopBtn.textContent = 'Stop Simulation';
        });
    }
    
    function checkSimulationStatusFull() {
        fetch('/sumo_ai/api/sumo/status')
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            if (data.status === 'running') {
                refreshStatistics();
                refreshVisualization();
            }
        })
        .catch(error => {
            console.error('Error checking full status:', error);
        });
    }
    
    function refreshStatistics() {
        const now = Date.now();
        if (now - lastStatisticsRefresh < STATS_REFRESH_INTERVAL) {
            return; // Too soon to refresh
        }
        
        lastStatisticsRefresh = now;
        
        fetch('/sumo_ai/api/sumo/statistics')
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            if (data.status === 'success') {
                const stats = data.statistics;
                let html = `
                    <div class="row">
                        <div class="col-md-6">
                            <div class="card bg-light mb-2">
                                <div class="card-body">
                                    <h6>Vehicles</h6>
                                    <p class="card-text" id="vehicle-count">${stats.total_vehicles}</p>
                                </div>
                            </div>
                        </div>
                        <div class="col-md-6">
                            <div class="card bg-light mb-2">
                                <div class="card-body">
                                    <h6>Avg Speed</h6>
                                    <p class="card-text">${stats.average_speed} km/h</p>
                                </div>
                            </div>
                        </div>
                        <div class="text-center p-4 bg-gray-50 rounded-lg">
                            <div class="text-2xl font-bold text-gray-900" id="co2-emissions">${stats.total_co2_emission} mg</div>
                            <div class="text-sm text-gray-500">CO₂ Emissions</div>
                        </div>
                        <div class="col-md-6">
                            <div class="card bg-light mb-2">
                                <div class="card-body">
                                    <h6>Congestion Level</h6>
                                    <p class="card-text">${getCongestionLabel(stats.congestion_level)}</p>
                                </div>
                            </div>
                        </div>
                        <div class="text-center p-4 bg-gray-50 rounded-lg">
                            <small class="text-muted">Simulation step: ${stats.simulation_step}, Time: </small>
                            <div class="text-2xl font-bold text-gray-900" id="simulation-time">${stats.simulation_time}</div>
                        </div>
                    </div>

                `;
                document.getElementById('simulation-stats').innerHTML = html;
            } else {
                document.getElementById('simulation-stats').innerHTML = '<p class="text-muted">Unable to load statistics</p>';
            }
        })
        .catch(error => {
            console.error('Error getting statistics:', error);
            document.getElementById('simulation-stats').innerHTML = '<p class="text-muted">Error loading statistics</p>';
        });
    }
    
    function refreshVisualization() {
        const now = Date.now();
        if (now - lastVisualizationRefresh < VIZ_REFRESH_INTERVAL) {
            return; // Too soon to refresh
        }
        
        lastVisualizationRefresh = now;
        
        fetch('/sumo_ai/api/sumo/status')
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            if (data.status === 'running') {
                const vehicles = data.vehicles;
                const trafficLights = data.traffic_lights;
                
                let html = `
                    <div class="d-flex justify-content-between mb-3">
                        <span><strong>Vehicles:</strong> ${Object.keys(vehicles).length}</span>
                        <span><strong>Traffic Lights:</strong> ${Object.keys(trafficLights).length}</span>
                        <span><strong>Simulation Step:</strong> ${data.step}</span>
                    </div>
                    <div class="progress mb-3">
                        <div class="progress-bar" role="progressbar" 
                             style="width: ${(data.step % 100)}%" 
                             aria-valuenow="${data.step % 100}" 
                             aria-valuemin="0" 
                             aria-valuemax="100">
                            ${data.step % 100}%
                        </div>
                    </div>
                    <div class="text-center">
                        <p class="text-muted">Real-time visualization would appear here</p>
                        <p><small>Showing simulation data from ${new Date(data.time).toLocaleTimeString()}</small></p>
                    </div>
                `;
                document.getElementById('visualization-container').innerHTML = html;
            }
        })
        .catch(error => {
            console.error('Error refreshing visualization:', error);
        });
    }
    
    function controlTrafficLight(e) {
        e.preventDefault();
        
        const tlId = document.getElementById('tl-id').value;
        const state = document.getElementById('tl-state').value;
        const duration = document.getElementById('tl-duration').value;
        
        fetch('/sumo_ai/api/sumo/control/traffic_light', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                tl_id: tlId,
                state: state,
                duration: duration
            })
        })
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            if (data.status === 'success') {
                showNotification('Traffic light updated successfully', 'success');
            } else {
                showNotification('Error: ' + data.message, 'error');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            showNotification('Error updating traffic light: ' + error.message, 'error');
        });
    }
    
    function runTrafficPrediction() {
        runPredictionBtn.disabled = true;
        runPredictionBtn.textContent = 'Predicting...';
        
        fetch('/sumo_ai/api/ai/predict/traffic', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                steps: 4
            })
        })
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            if (data.status === 'success') {
                displayPredictionResults(data);
            } else {
                showNotification('Prediction failed: ' + data.error, 'error');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            showNotification('Error running prediction: ' + error.message, 'error');
        })
        .finally(() => {
            runPredictionBtn.disabled = false;
            runPredictionBtn.textContent = 'Predict Next Hour';
        });
    }
    
    function refreshAIPerformance() {
        refreshPerformanceBtn.disabled = true;
        refreshPerformanceBtn.textContent = 'Refreshing...';
        
        fetch('/sumo_ai/api/ai/performance')
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            if (data.status === 'success') {
                displayAIPerformance(data.metrics);
            } else {
                showNotification('Failed to get AI performance', 'error');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            showNotification('Error getting AI performance: ' + error.message, 'error');
        })
        .finally(() => {
            refreshPerformanceBtn.disabled = false;
            refreshPerformanceBtn.textContent = 'Refresh Metrics';
        });
    }
    
    function displayPredictionResults(data) {
        const container = document.getElementById('traffic-prediction');
        const predictions = data.predictions;
        
        let html = `
            <div class="mb-2">
                <strong>Traffic Predictions:</strong>
            </div>
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
        
        html += `</ul>`;
        container.innerHTML = html;
    }
    
    function displayAIPerformance(metrics) {
        const container = document.getElementById('ai-performance');
        
        let html = `
            <div class="row">
                <div class="col-md-6">
                    <div class="card bg-light mb-2">
                        <div class="card-body">
                            <h6>Accuracy</h6>
                            <p class="card-text">${(metrics.accuracy * 100).toFixed(1)}%</p>
                        </div>
                    </div>
                </div>
                <div class="col-md-6">
                    <div class="card bg-light mb-2">
                        <div class="card-body">
                            <h6>F1 Score</h6>
                            <p class="card-text">${metrics.f1_score.toFixed(3)}</p>
                        </div>
                    </div>
                </div>
                <div class="col-md-6">
                    <div class="card bg-light mb-2">
                        <div class="card-body">
                            <h6>Response Time</h6>
                            <p class="card-text">${metrics.response_time}</p>
                        </div>
                    </div>
                </div>
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
    
    function showNotification(message, type) {
        // Create and show a Bootstrap toast notification
        const toastContainer = document.getElementById('toast-container') || createToastContainer();
        const toastId = 'toast-' + Date.now();
        
        const toastHTML = `
            <div class="toast ${type === 'error' ? 'bg-danger' : 'bg-success'} text-white" id="${toastId}" role="alert" aria-live="assertive" aria-atomic="true">
                <div class="toast-header">
                    <strong class="me-auto">${type === 'error' ? 'Error' : 'Success'}</strong>
                    <button type="button" class="btn-close" data-bs-dismiss="toast" aria-label="Close"></button>
                </div>
                <div class="toast-body">
                    ${message}
                </div>
            </div>
        `;
        
        toastContainer.innerHTML += toastHTML;
        const toastElement = document.getElementById(toastId);
        const toast = new bootstrap.Toast(toastElement);
        toast.show();
    }
    
    function createToastContainer() {
        const container = document.createElement('div');
        container.id = 'toast-container';
        container.className = 'toast-container position-fixed top-0 end-0 p-3';
        container.style.zIndex = '1050';
        document.body.appendChild(container);
        return container;
    }
});