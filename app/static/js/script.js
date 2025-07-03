    // Mobile menu toggle
        document.addEventListener('DOMContentLoaded', function() {
            const mobileMenuBtn = document.querySelector('.mobile-menu-btn');
            const sidebar = document.querySelector('.sidebar');
            
            mobileMenuBtn.addEventListener('click', function() {
                sidebar.classList.toggle('active');
            });

            // Simulate traffic map
            const trafficMap = document.getElementById('trafficMap');
            if (trafficMap) {
                simulateTrafficMap(trafficMap);
            }

            // Add active class to clicked nav items
            const navLinks = document.querySelectorAll('.nav-link');
            navLinks.forEach(link => {
                link.addEventListener('click', function(e) {
                    e.preventDefault();
                    navLinks.forEach(l => l.classList.remove('active'));
                    this.classList.add('active');
                });
            });

            // Map controls
            const mapControls = document.querySelectorAll('.map-control-btn');
            mapControls.forEach(control => {
                control.addEventListener('click', function() {
                    mapControls.forEach(c => c.classList.remove('active'));
                    this.classList.add('active');
                });
            });
        });

        function simulateTrafficMap(container) {
            // Clear container
            container.innerHTML = '';

            // Create roads
            const horizontalRoad = document.createElement('div');
            horizontalRoad.className = 'road horizontal';
            container.appendChild(horizontalRoad);

            const verticalRoad = document.createElement('div');
            verticalRoad.className = 'road vertical';
            container.appendChild(verticalRoad);

            // Create intersection
            const intersection = document.createElement('div');
            intersection.className = 'intersection';
            intersection.style.left = '50%';
            intersection.style.top = '50%';
            container.appendChild(intersection);

            // Create traffic lights
            const lightPositions = [
                { left: '50%', top: '30%', color: 'red' },
                { left: '70%', top: '50%', color: 'green' },
                { left: '50%', top: '70%', color: 'red' },
                { left: '30%', top: '50%', color: 'green' }
            ];

            lightPositions.forEach(pos => {
                const light = document.createElement('div');
                light.className = `traffic-light ${pos.color}`;
                light.style.left = pos.left;
                light.style.top = pos.top;
                if (pos.color === 'red' || pos.color === 'green') {
                    light.classList.add('pulse');
                }
                container.appendChild(light);
            });

            // Create camera markers
            const cameraPositions = [
                { left: '20%', top: '30%', id: 'CAM-01' },
                { left: '80%', top: '40%', id: 'CAM-02' },
                { left: '60%', top: '70%', id: 'CAM-03' },
                { left: '40%', top: '20%', id: 'CAM-04' }
            ];

            cameraPositions.forEach(pos => {
                const camera = document.createElement('div');
                camera.className = 'camera-marker';
                camera.style.left = pos.left;
                camera.style.top = pos.top;
                camera.innerHTML = `<i class="fas fa-video" style="transform: rotate(45deg); position: relative; z-index: 1;"></i>`;
                container.appendChild(camera);
            });

            // Create vehicles
            const vehicles = [
                { left: '15%', top: '50%', color: '#0A84FF', direction: 'right' },
                { left: '85%', top: '50%', color: '#FF375F', direction: 'left' },
                { left: '50%', top: '15%', color: '#30D158', direction: 'down' },
                { left: '50%', top: '85%', color: '#FF9F0A', direction: 'up' },
                { left: '25%', top: '50%', color: '#5AC8FA', direction: 'right' },
                { left: '75%', top: '50%', color: '#BF5AF2', direction: 'left' }
            ];

            vehicles.forEach(vehicle => {
                const veh = document.createElement('div');
                veh.className = 'vehicle';
                veh.style.left = vehicle.left;
                veh.style.top = vehicle.top;
                veh.style.backgroundColor = vehicle.color;
                container.appendChild(veh);

                // Animate vehicle
                if (vehicle.direction === 'right') {
                    animateVehicle(veh, { left: '15%' }, { left: '85%' }, 10000);
                } else if (vehicle.direction === 'left') {
                    animateVehicle(veh, { left: '85%' }, { left: '15%' }, 10000);
                } else if (vehicle.direction === 'down') {
                    animateVehicle(veh, { top: '15%' }, { top: '85%' }, 10000);
                } else if (vehicle.direction === 'up') {
                    animateVehicle(veh, { top: '85%' }, { top: '15%' }, 10000);
                }
            });

            function animateVehicle(element, from, to, duration) {
                const startTime = performance.now();
                
                function updateAnimation(time) {
                    const elapsed = time - startTime;
                    const progress = Math.min(elapsed / duration, 1);
                    
                    if (from.left && to.left) {
                        const start = parseFloat(from.left);
                        const end = parseFloat(to.left);
                        const current = start + (end - start) * progress;
                        element.style.left = `${current}%`;
                    }
                    
                    if (from.top && to.top) {
                        const start = parseFloat(from.top);
                        const end = parseFloat(to.top);
                        const current = start + (end - start) * progress;
                        element.style.top = `${current}%`;
                    }
                    
                    if (progress < 1) {
                        requestAnimationFrame(updateAnimation);
                    } else {
                        // Reverse direction when animation completes
                        if (from.left && to.left) {
                            animateVehicle(element, to, from, duration);
                        } else if (from.top && to.top) {
                            animateVehicle(element, to, from, duration);
                        }
                    }
                }
                
                requestAnimationFrame(updateAnimation);
            }

            // Change traffic lights periodically
            setInterval(() => {
                const lights = container.querySelectorAll('.traffic-light');
                lights.forEach(light => {
                    if (light.classList.contains('red')) {
                        light.classList.remove('red', 'pulse');
                        light.classList.add('yellow');
                        setTimeout(() => {
                            light.classList.remove('yellow');
                            light.classList.add('green');
                            light.classList.add('pulse');
                        }, 2000);
                    } else if (light.classList.contains('green')) {
                        light.classList.remove('green', 'pulse');
                        light.classList.add('yellow');
                        setTimeout(() => {
                            light.classList.remove('yellow');
                            light.classList.add('red');
                            light.classList.add('pulse');
                        }, 2000);
                    }
                });
            }, 15000);
        }


// Simple animation on load
    document.addEventListener('DOMContentLoaded', function() {
        const inputs = document.querySelectorAll('.form-control');
        inputs.forEach(input => {
            input.addEventListener('focus', function() {
                this.parentElement.querySelector('i').style.color = var(--primary);
            });
            
            input.addEventListener('blur', function() {
                this.parentElement.querySelector('i').style.color = var(--gray);
            });
        });
    });