// static/js/auth.js
function checkTokenExpiration() {
    function parseJwt(token) {
        try {
            return JSON.parse(atob(token.split('.')[1]));
        } catch (e) {
            return null;
        }
    }
    
    // Check access token in cookies
    const token = document.cookie.split('; ')
        .find(row => row.startsWith('access_token_cookie='))
        ?.split('=')[1];
    
    if (token) {
        const payload = parseJwt(token);
        if (payload && payload.exp) {
            const now = Math.floor(Date.now() / 1000);
            
            if (payload.exp < now) {
                // Token already expired
                window.location.href = "/login?expired=true&next=" + encodeURIComponent(window.location.pathname);
            } else if (payload.exp - now < 300) {
                // Token will expire in 5 minutes
                fetch('/auth/refresh', {
                    credentials: 'include'
                }).catch(() => {
                    window.location.href = "/login?session=expired";
                });
            }
        }
    }
}

// Check every 60 seconds
setInterval(checkTokenExpiration, 60000);
document.addEventListener('DOMContentLoaded', checkTokenExpiration);

// Show warning 2 minutes before expiration
function showTimeoutWarning(secondsUntilExpire) {
    if (secondsUntilExpire < 120) {
        // Display a modal or notification
        alert('Your session will expire soon. Click OK to stay logged in.');
        
        // Optionally refresh the token
        fetch('/auth/refresh', {
            method: 'POST',
            credentials: 'include'
        });
    }
}