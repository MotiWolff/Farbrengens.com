// View Toggle
document.querySelectorAll('.view-toggle button').forEach(button => {
    button.addEventListener('click', () => {
        document.querySelectorAll('.view-toggle button').forEach(b => b.classList.remove('active'));
        button.classList.add('active');
        
        const view = button.dataset.view;
        document.querySelector('#list-view').classList.toggle('active', view === 'list');
        document.querySelector('#map-view').classList.toggle('active', view === 'map');
        
        if (view === 'map') {
            setTimeout(initMap, 100);
        }
    });
});

// Favorite Toggle
document.querySelectorAll('.favorite-btn').forEach(button => {
    button.addEventListener('click', async () => {
        const eventId = button.dataset.eventId;
        const response = await fetch(`/api/favorite/${eventId}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            }
        });
        const data = await response.json();
        if (data.status === 'success') {
            button.querySelector('i').classList.toggle('fas');
            button.querySelector('i').classList.toggle('far');
        }
    });
});

// Share functionality
document.querySelectorAll('.share-btn').forEach(button => {
    button.addEventListener('click', async () => {
        if (navigator.share) {
            try {
                await navigator.share({
                    title: 'התוועדות נקודתית',
                    text: 'בוא להשתתף בהתוועדות!',
                    url: window.location.href,
                });
            } catch (err) {
                console.error('Error sharing:', err);
            }
        }
    });
});

// Map initialization
function initMap() {
    if (!document.getElementById('map')) return;
    
    // Create map centered on Israel
    const map = L.map('map').setView([31.7683, 35.2137], 7);
    
    // Add OpenStreetMap tiles
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap contributors'
    }).addTo(map);

    // Add markers for each event
    events.forEach(event => {
        if (event.coordinates) {
            const marker = L.marker([event.coordinates.lat, event.coordinates.lng])
                .bindPopup(`
                    <div class="map-popup">
                        <h3>${event.title}</h3>
                        <p><i class="fas fa-map-marker-alt"></i> ${event.location}</p>
                        <p><i class="fas fa-calendar"></i> ${event.date}</p>
                        <p><i class="fas fa-clock"></i> ${event.time}</p>
                        <p><i class="fas fa-user"></i> ${event.speaker}</p>
                        <a href="https://waze.com/ul?q=${encodeURIComponent(event.address)}" 
                           target="_blank" class="waze-link">
                           <i class="fas fa-map-marked-alt"></i> נווט
                        </a>
                    </div>
                `)
                .addTo(map);
        }
    });
}

function removeImage() {
    if (confirm('האם אתה בטוח שברצונך להסיר את התמונה?')) {
        document.getElementById('remove_image').value = 'true';
        document.querySelector('.current-image').style.display = 'none';
    }
}

// Newsletter subscription
document.getElementById('newsletter-form')?.addEventListener('submit', async (e) => {
    e.preventDefault();
    const form = e.target;
    const messageDiv = document.getElementById('newsletter-message');
    
    try {
        const response = await fetch('/subscribe', {
            method: 'POST',
            body: new FormData(form)
        });
        
        const data = await response.json();
        messageDiv.textContent = data.message;
        messageDiv.className = `alert alert-${data.status}`;
        messageDiv.style.display = 'block';
        
        if (data.status === 'success') {
            form.reset();
            setTimeout(() => {
                messageDiv.style.display = 'none';
            }, 5000);
        }
    } catch (error) {
        messageDiv.textContent = 'אירעה שגיאה בהרשמה לניוזלטר';
        messageDiv.className = 'alert alert-error';
        messageDiv.style.display = 'block';
    }
});