document.addEventListener('DOMContentLoaded', function() {
    // Initialize map (in a real app, this would use Leaflet or Google Maps)
    const mapContainer = document.getElementById('locationsMap');
    if (mapContainer) {
        // This is where you would initialize your map library
        console.log('Map container ready for initialization');
    }

    // Location card click handlers
    const locationCards = document.querySelectorAll('.location-card');
    locationCards.forEach(card => {
        card.addEventListener('click', function(e) {
            // Don't trigger if clicking on an action button
            if (e.target.tagName === 'BUTTON' || e.target.closest('button')) {
                return;
            }
            
            const locationName = this.querySelector('h3').textContent;
            console.log(`Viewing details for ${locationName}`);
            // In real implementation, this would open a detail view or modal
        });
    });

    // Filter functionality
    const searchInput = document.querySelector('.location-search input');
    if (searchInput) {
        searchInput.addEventListener('input', function() {
            const searchTerm = this.value.toLowerCase();
            filterLocations(searchTerm);
        });
    }

    function filterLocations(searchTerm) {
        locationCards.forEach(card => {
            const locationName = card.querySelector('h3').textContent.toLowerCase();
            const locationId = card.querySelector('.detail-value').textContent.toLowerCase();
            
            if (locationName.includes(searchTerm) || locationId.includes(searchTerm)) {
                card.style.display = 'block';
            } else {
                card.style.display = 'none';
            }
        });
    }

    // Export button
    const exportBtn = document.querySelector('button:has(.ri-download-line)');
    if (exportBtn) {
        exportBtn.addEventListener('click', function() {
            alert('Exporting location data...');
            // In real implementation, this would generate a CSV or PDF
        });
    }

    // Add location button
    const addLocationBtn = document.querySelector('button:has(.ri-add-line)');
    if (addLocationBtn) {
        addLocationBtn.addEventListener('click', function() {
            console.log('Opening add location form');
            // In real implementation, this would open a modal form
        });
    }
});

    document.addEventListener('DOMContentLoaded', function() {
    // Toggle camera registration form
    const addCameraBtn = document.querySelector('button:has(.ri-add-line)');
    const cancelRegistrationBtn = document.getElementById('cancelRegistration');
    const registrationForm = document.getElementById('cameraRegistrationForm');
    
    if (addCameraBtn && registrationForm) {
        addCameraBtn.addEventListener('click', function() {
            registrationForm.classList.remove('hidden');
            window.scrollTo({
                top: registrationForm.offsetTop - 20,
                behavior: 'smooth'
            });
        });
    }
    
    if (cancelRegistrationBtn && registrationForm) {
        cancelRegistrationBtn.addEventListener('click', function() {
            registrationForm.classList.add('hidden');
        });
    }

    // Test RTSP stream buttons
    const testRtspButtons = document.querySelectorAll('.rtsp-test-btn');
    testRtspButtons.forEach(button => {
        button.addEventListener('click', function(e) {
            e.stopPropagation();
            const cameraCard = this.closest('.camera-card');
            const cameraId = cameraCard.querySelector('h3').textContent;
            alert(`Testing RTSP stream for ${cameraId}`);
            // In real implementation, this would ping the camera stream
        });
    });

});

document.addEventListener('DOMContentLoaded', function() {
    // Initialize signal timing chart
    const signalTimingChart = echarts.init(document.getElementById('signalTimingChart'));
    const option = {
        animation: false,
        tooltip: {
            trigger: 'axis',
            backgroundColor: 'rgba(255, 255, 255, 0.9)',
            borderColor: '#e2e8f0',
            textStyle: {
                color: '#1f2937'
            }
        },
        legend: {
            data: ['North-South Green', 'East-West Green', 'Cycle Length'],
            textStyle: {
                color: '#1f2937'
            },
            right: 0
        },
        grid: {
            left: '3%',
            right: '3%',
            bottom: '3%',
            top: '15%',
            containLabel: true
        },
        xAxis: {
            type: 'category',
            data: ['6a', '7a', '8a', '9a', '10a', '11a', '12p', '1p', '2p', '3p', '4p', '5p', '6p'],
            axisLine: {
                lineStyle: {
                    color: '#e2e8f0'
                }
            },
            axisLabel: {
                color: '#64748b'
            }
        },
        yAxis: {
            type: 'value',
            name: 'Seconds',
            axisLine: {
                show: false
            },
            axisLabel: {
                color: '#64748b'
            },
            splitLine: {
                lineStyle: {
                    color: '#e2e8f0'
                }
            }
        },
        series: [
            {
                name: 'North-South Green',
                type: 'line',
                smooth: true,
                lineStyle: {
                    width: 3,
                    color: 'rgba(16, 185, 129, 1)'
                },
                symbol: 'none',
                data: [40, 45, 50, 45, 40, 40, 40, 40, 40, 40, 40, 45, 50]
            },
            {
                name: 'East-West Green',
                type: 'line',
                smooth: true,
                lineStyle: {
                    width: 3,
                    color: 'rgba(239, 68, 68, 1)'
                },
                symbol: 'none',
                data: [30, 25, 20, 25, 30, 30, 30, 30, 30, 30, 30, 25, 20]
            },
            {
                name: 'Cycle Length',
                type: 'line',
                smooth: true,
                lineStyle: {
                    width: 2,
                    color: 'rgba(59, 130, 246, 1)',
                    type: 'dashed'
                },
                symbol: 'none',
                data: [120, 120, 130, 120, 120, 120, 120, 120, 120, 120, 120, 120, 130]
            }
        ]
    };
    signalTimingChart.setOption(option);
    window.addEventListener('resize', function() {
        signalTimingChart.resize();
    });

    // Signal box interactions
    const signalBoxes = document.querySelectorAll('.signal-box');
    signalBoxes.forEach(box => {
        box.addEventListener('click', function() {
            const direction = this.getAttribute('data-direction');
            alert(`Showing detailed controls for ${direction} signal`);
        });
    });

    // Control mode buttons
    const controlModeButtons = document.querySelectorAll('.flex.items-center.space-x-3 button');
    controlModeButtons.forEach(button => {
        button.addEventListener('click', function() {
            controlModeButtons.forEach(btn => {
                btn.classList.remove('bg-primary', 'text-white', 'border-primary', 'text-primary');
                btn.classList.add('border-slate-200');
            });
            
            if (this.textContent === 'AI Auto') {
                this.classList.add('bg-primary', 'text-white');
                this.classList.remove('border-slate-200');
            } else {
                this.classList.add('border-primary', 'text-primary');
                this.classList.remove('border-slate-200');
            }
        });
    });
});

document.addEventListener('DOMContentLoaded', function() {

    // Form input listeners for live preview
    const previewFields = [
        { input: 'location-name', preview: 'preview-name' },
        { input: 'location-id', preview: 'preview-id' },
        { input: 'location-zone', preview: 'preview-zone' },
        { input: 'location-priority', preview: 'preview-priority' },
        { input: 'location-address', preview: 'preview-address' }
    ];
    
    previewFields.forEach(field => {
        const inputElement = document.getElementById(field.input);
        if (inputElement) {
            inputElement.addEventListener('input', updatePreview);
        }
    });
    
    // Coordinate inputs
    const latInput = document.getElementById('location-lat');
    const lngInput = document.getElementById('location-lng');
    
    if (latInput && lngInput) {
        latInput.addEventListener('input', updateCoordinatesPreview);
        lngInput.addEventListener('input', updateCoordinatesPreview);
    }
    
    // Map click handler (simulated)
    const mapPreview = document.querySelector('.map-preview');
    if (mapPreview) {
        mapPreview.addEventListener('click', function(e) {
            // In a real app, this would get actual coordinates from the map click
            const lat = (Math.random() * 180 - 90).toFixed(6);
            const lng = (Math.random() * 360 - 180).toFixed(6);
            
            latInput.value = lat;
            lngInput.value = lng;
            
            updateCoordinatesPreview();
        });
    }
    
    // Update preview function
    function updatePreview() {
        previewFields.forEach(field => {
            const inputElement = document.getElementById(field.input);
            const previewElement = document.getElementById(field.preview);
            
            if (inputElement && previewElement) {
                if (inputElement.tagName === 'SELECT') {
                    const selectedOption = inputElement.options[inputElement.selectedIndex];
                    previewElement.textContent = selectedOption.text;
                } else {
                    previewElement.textContent = inputElement.value || '-';
                }
            }
        });
        
        // Update location type in preview
        const selectedType = document.querySelector('.location-type-option.selected');
        if (selectedType) {
            document.getElementById('preview-type').textContent = 
                selectedType.querySelector('h3').textContent;
        }
    }
    
    function updateCoordinatesPreview() {
        const lat = latInput.value;
        const lng = lngInput.value;
        
        if (lat && lng) {
            document.getElementById('preview-coords').textContent = `${lat}, ${lng}`;
        } else {
            document.getElementById('preview-coords').textContent = '-';
        }
    }
    
    // Initialize preview
    updatePreview();
});