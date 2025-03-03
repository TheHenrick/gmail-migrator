/**
 * Gmail Migrator - Main JavaScript
 */

document.addEventListener('DOMContentLoaded', () => {
    // UI Elements
    const connectGmailBtn = document.getElementById('connectGmail');
    const connectDestinationBtn = document.getElementById('connectDestination');
    const startMigrationBtn = document.getElementById('startMigration');
    const accountOptions = document.querySelectorAll('.account-option');

    // State
    let isGmailConnected = false;
    let isDestinationConnected = false;
    let selectedDestination = null;

    // Connect Gmail button
    connectGmailBtn.addEventListener('click', async () => {
        try {
            // In a real app, this would redirect to OAuth flow
            console.log('Connecting to Gmail...');
            connectGmailBtn.textContent = 'Connecting...';

            // Simulate API call
            await new Promise(resolve => setTimeout(resolve, 1500));

            // Update UI to show connected state
            connectGmailBtn.textContent = 'Connected to Gmail';
            connectGmailBtn.classList.remove('primary');
            connectGmailBtn.classList.add('secondary');

            isGmailConnected = true;
            updateUI();
        } catch (error) {
            console.error('Error connecting to Gmail:', error);
            connectGmailBtn.textContent = 'Connect Gmail';
        }
    });

    // Destination account selection
    accountOptions.forEach(option => {
        if (option.closest('.source-section')) return; // Skip source options

        option.addEventListener('click', () => {
            // Remove selection from all options
            accountOptions.forEach(opt => {
                if (opt.closest('.destination-section')) {
                    opt.classList.remove('selected');
                }
            });

            // Add selection to clicked option
            option.classList.add('selected');

            // Get the selected service
            const serviceName = option.querySelector('span').textContent;
            selectedDestination = serviceName;

            // Update UI
            connectDestinationBtn.textContent = `Connect ${serviceName}`;
            connectDestinationBtn.disabled = false;

            updateUI();
        });
    });

    // Connect destination button
    connectDestinationBtn.addEventListener('click', async () => {
        if (!selectedDestination) return;

        try {
            // In a real app, this would redirect to OAuth flow
            console.log(`Connecting to ${selectedDestination}...`);
            connectDestinationBtn.textContent = 'Connecting...';

            // Simulate API call
            await new Promise(resolve => setTimeout(resolve, 1500));

            // Update UI to show connected state
            connectDestinationBtn.textContent = `Connected to ${selectedDestination}`;
            connectDestinationBtn.classList.remove('primary');
            connectDestinationBtn.classList.add('secondary');

            isDestinationConnected = true;
            updateUI();
        } catch (error) {
            console.error(`Error connecting to ${selectedDestination}:`, error);
            connectDestinationBtn.textContent = `Connect ${selectedDestination}`;
        }
    });

    // Start migration button
    startMigrationBtn.addEventListener('click', async () => {
        if (!isGmailConnected || !isDestinationConnected) return;

        try {
            // Collect migration options
            const options = {
                preserveFolders: document.getElementById('preserveFolders').checked,
                includeAttachments: document.getElementById('includeAttachments').checked,
                onlyUnread: document.getElementById('onlyUnread').checked,
                startDate: document.getElementById('startDate').value || null,
                endDate: document.getElementById('endDate').value || null
            };

            console.log('Starting migration with options:', options);
            startMigrationBtn.textContent = 'Migration in progress...';
            startMigrationBtn.disabled = true;

            // In a real app, this would call the API to start migration
            // For now, we'll just simulate progress
            simulateMigrationProgress();
        } catch (error) {
            console.error('Error starting migration:', error);
            startMigrationBtn.textContent = 'Start Migration';
            startMigrationBtn.disabled = false;
        }
    });

    // Update UI based on current state
    function updateUI() {
        if (isGmailConnected && isDestinationConnected) {
            startMigrationBtn.disabled = false;
        } else {
            startMigrationBtn.disabled = true;
        }
    }

    // Simulate migration progress (for demo purposes)
    async function simulateMigrationProgress() {
        // In a real app, this would be replaced with actual API calls
        // to check migration progress

        // Create a progress element
        const main = document.querySelector('main');
        const progressSection = document.createElement('section');
        progressSection.className = 'card progress-card';
        progressSection.innerHTML = `
            <h2>Migration Progress</h2>
            <div class="progress-container">
                <div class="progress-bar" style="width: 0%"></div>
            </div>
            <p class="progress-text">0% complete</p>
            <p class="migration-stats">Emails processed: 0</p>
        `;

        main.appendChild(progressSection);

        const progressBar = progressSection.querySelector('.progress-bar');
        const progressText = progressSection.querySelector('.progress-text');
        const migrationStats = progressSection.querySelector('.migration-stats');

        // Simulate progress
        let progress = 0;
        let emailCount = 0;

        const interval = setInterval(() => {
            progress += Math.random() * 5;
            emailCount = Math.floor(progress * 8);

            if (progress >= 100) {
                progress = 100;
                clearInterval(interval);
                startMigrationBtn.textContent = 'Migration Complete';

                // Add a success message
                const successMessage = document.createElement('p');
                successMessage.className = 'success-message';
                successMessage.textContent = 'Migration completed successfully!';
                progressSection.appendChild(successMessage);
            }

            progressBar.style.width = `${progress}%`;
            progressText.textContent = `${Math.floor(progress)}% complete`;
            migrationStats.textContent = `Emails processed: ${emailCount}`;
        }, 500);
    }
});
