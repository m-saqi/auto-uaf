        document.addEventListener('DOMContentLoaded', function() {
      // Elements
      const resultForm = document.getElementById('resultForm');
      const registrationNumber = document.getElementById('registrationNumber');
      const resultContainer = document.getElementById('resultContainer');
      const statusLog = document.getElementById('statusLog');
      const themeToggle = document.getElementById('themeToggle');
      const cursorDot = document.getElementById('cursorDot');
      const contactForm = document.getElementById('contact-form');
      const downloadLogBtn = document.getElementById('downloadLogBtn');
      const clearLogBtn = document.getElementById('clearLogBtn');
      const semesterResults = document.getElementById('semesterResults');
      const studentName = document.getElementById('studentName');
      const studentReg = document.getElementById('studentReg');
      const totalCgpa = document.getElementById('totalCgpa');
      const totalPercentage = document.getElementById('totalPercentage');
      const totalMarksObtained = document.getElementById('totalMarksObtained');
      const totalMaxMarks = document.getElementById('totalMaxMarks');
      const downloadPdfBtn = document.getElementById('downloadPdfBtn');
      const courseDetailsModal = new bootstrap.Modal(document.getElementById('courseDetailsModal'));
      const addCourseModal = new bootstrap.Modal(document.getElementById('addCourseModal'));
      const saveCourseBtn = document.getElementById('saveCourseBtn');
      const addCourseForm = document.getElementById('addCourseForm');
      const loadingContainer = document.getElementById('loadingContainer');
      const backToTopButton = document.getElementById('backToTop');
      const addForecastSemesterBtn = document.getElementById('addForecastSemesterBtn');
      const gpaChartContainer = document.getElementById('gpaChartContainer');
      const gpaTrendChartCanvas = document.getElementById('gpaTrendChart').getContext('2d');
      const profileManagementDiv = document.getElementById('profileManagement');
      const profileSwitcher = document.getElementById('profileSwitcher');
      const renameProfileModal = new bootstrap.Modal(document.getElementById('renameProfileModal'));
      const saveProfileNameBtn = document.getElementById('saveProfileNameBtn');

      let renameSemesterModal; // Will be initialized in init()
      let saveSemesterNameBtn; // Will be initialized in init()

      // NEW Attendance System Elements
      let fetchAttendanceBtn = document.getElementById('fetchAttendanceBtn');
      let bedFetchAttendanceBtn = document.getElementById('bed-fetchAttendanceBtn');
      let otherFetchAttendanceBtn = document.getElementById('other-fetchAttendanceBtn');
      const attendanceImportModal = new bootstrap.Modal(document.getElementById('attendanceImportModal'));
      const importAttendanceCoursesBtn = document.getElementById('importAttendanceCoursesBtn');

      // Profile Manager Elements
      const openProfileManagerBtn = document.getElementById('openProfileManagerBtn');
      const profileManagerModal = new bootstrap.Modal(document.getElementById('profileManagerModal'));
      const profileManagerModalEl = document.getElementById('profileManagerModal'); // Get the element
      const renameProfileModalEl = document.getElementById('renameProfileModal'); // Get the element
      const confirmationModal = new bootstrap.Modal(document.getElementById('confirmationModal'));
      const confirmationModalEl = document.getElementById('confirmationModal'); // Get the element
      const attendanceImportModalEl = document.getElementById('attendanceImportModal'); // Get the element

      // Import/Export buttons
      const importProfilesBtn = document.getElementById('importProfilesBtn');
      const exportProfilesBtn = document.getElementById('exportProfilesBtn');
      const importProfilesBtnModal = document.getElementById('importProfilesBtnModal'); // In modal
      const exportProfilesBtnModal = document.getElementById('exportProfilesBtnModal'); // In modal

      // State
      let allLogs = [];
      let processedData = null;
      let deletedSemesters = {};
      let gpaChart = null;
      let bedGpaChart = null;
      let otherGpaChart = null;
      let isInitialLoad = true;
      let confirmationCallback = null;
      let importedAttendanceCourses = []; // Tracks courses from the last import

      // --- NEW B.Ed. Variables ---
      const BED_COURSES = new Set([
        'EDU-501', 'EDU-503', 'EDU-505', 'EDU-507', 'EDU-509', 'EDU-511', 'EDU-513',
        'EDU-502', 'EDU-504', 'EDU-506', 'EDU-508', 'EDU-510', 'EDU-512', 'EDU-516',
        'EDU-601', 'EDU-604', 'EDU-605', 'EDU-607', 'EDU-608', 'EDU-623'
      ]);
      let bedConfirmationModal; // Will be initialized in init()
      let bedModeActive = false;
      // --- End of NEW B.Ed. Variables ---

      const API_ENDPOINT = `/api/result-scraper?action=scrape_single`;
      const ATTENDANCE_API_ENDPOINT = `/api/result-scraper?action=scrape_attendance`; // NEW API Endpoint

          
          // NEW FUNCTION to auto-collapse mobile menu
function initMenuAutoCollapse() {
  const navLinks = document.querySelectorAll('#mainNav .nav-link');
  const togglerButton = document.querySelector('.navbar-toggler[data-bs-target="#mainNav"]');
  const collapsibleMenu = document.getElementById('mainNav');

  if (!togglerButton || !collapsibleMenu) return;

  navLinks.forEach(link => {
    link.addEventListener('click', () => {
      // Check if the menu is currently shown (Bootstrap 5 class)
      if (collapsibleMenu.classList.contains('show')) {
        togglerButton.click(); // Simulate a click on the toggler to close it
      }
    });
  });
}
      
          // NEW updated init() function
function init() {
  try {
    migrateOldProfiles(); 
    initCustomCursor();
    initTheme();
    
    renameSemesterModal = new bootstrap.Modal(document.getElementById('renameSemesterModal'));
    saveSemesterNameBtn = document.getElementById('saveSemesterNameBtn');
    saveSemesterNameBtn.addEventListener('click', renameSemester); 
    
    initContactForm();
    createToastContainer();
    initBackToTop();
    initScrollAnimations();
    loadProfiles(); 
    initModalZIndexHandlers(); 
    
    initMenuAutoCollapse(); // <-- ADD THIS LINE

    // --- NEW B.Ed. Modal Init ---
    const bedModalEl = document.getElementById('bedConfirmationModal');
    if (bedModalEl) {
        bedConfirmationModal = new bootstrap.Modal(bedModalEl);
        document.getElementById('bedConfirmYes').addEventListener('click', () => {
          console.log("B.Ed. Yes clicked");
        });
        document.getElementById('bedConfirmNo').addEventListener('click', () => {
           console.log("B.Ed. No clicked");
        });
    } else {
        console.warn("B.Ed. confirmation modal HTML not found.");
    }

  } catch (error) { 
      console.error("Initialization failed:", error);
      try {
          createToastContainer(); 
          showToast("Error initializing application. Saved data might be corrupted.", "error");
      } catch (toastError) {
          console.error("Could not show initialization error toast:", toastError);
      }
  }
}


      function setupAttendanceButton() {
        // We now have three buttons to update
        const buttons = [
            { el: fetchAttendanceBtn, id: 'fetchAttendanceBtn' },
            { el: bedFetchAttendanceBtn, id: 'bed-fetchAttendanceBtn' },
            { el: otherFetchAttendanceBtn, id: 'other-fetchAttendanceBtn' }
        ];

        buttons.forEach(btnInfo => {
            if (!btnInfo.el) {
                // Button might not exist in DOM yet, try to find it
                btnInfo.el = document.getElementById(btnInfo.id);
                if (!btnInfo.el) {
                    // console.warn(`Attendance button ${btnInfo.id} not found.`);
                    return; // Skip if still not found
                }
            }

            // Remove existing listener to avoid stacking
            const newBtn = btnInfo.el.cloneNode(true);
            btnInfo.el.parentNode.replaceChild(newBtn, btnInfo.el);
            btnInfo.el = newBtn; // Re-assign the variable
            
            // Re-assign global variables
            if (btnInfo.id === 'fetchAttendanceBtn') fetchAttendanceBtn = newBtn;
            else if (btnInfo.id === 'bed-fetchAttendanceBtn') bedFetchAttendanceBtn = newBtn;
            else if (btnInfo.id === 'other-fetchAttendanceBtn') otherFetchAttendanceBtn = newBtn;

            if (importedAttendanceCourses.length > 0) {
                newBtn.innerHTML = '<i class="fa-solid fa-rotate-left me-2"></i>Revert Import';
                newBtn.className = 'btn btn-danger-action'; // Use danger for revert
                // Pass the button itself to the revert function
                newBtn.addEventListener('click', (e) => revertAttendanceImport(e.currentTarget));
                newBtn.disabled = false; // Ensure it's enabled
            } else {
                newBtn.innerHTML = '<i class="fa-solid fa-clipboard-user me-2"></i>Attendance System';
                newBtn.className = 'btn btn-success-action';
                // Pass the button itself to the fetch function
                newBtn.addEventListener('click', (e) => fetchAttendanceData(e.currentTarget));
                // Only disable if there is no processedData
                newBtn.disabled = !processedData;
            }
            
            // Re-apply styles
            newBtn.style.minWidth = '220px';
            newBtn.style.borderRadius = 'var(--radius-btn)';
        });
      }

      function revertAttendanceImport() {
        if (importedAttendanceCourses.length === 0) return;

        let revertedCount = 0;
        importedAttendanceCourses.forEach(imported => {
            const semester = processedData.semesters[imported.semester];
            if (semester) {
                const initialLength = semester.courses.length;
                semester.courses = semester.courses.filter(c => 
                    !(c.isCustom && c.source === 'attendance' && c.code === imported.code)
                );
                if (semester.courses.length < initialLength) {
                    revertedCount++;
                }
            }
        });
        
        showToast(`Reverted ${revertedCount} imported course(s)`, 'success');
        addStatusMessage(`Reverted import of ${revertedCount} courses`, 'info');
        
        importedAttendanceCourses = []; // Clear the list
        recalculateAndDisplay(); // This saves the profile
        setupAttendanceButton(); // Reset the button
      }

      function updateAttendanceCounts() {
        const listEl = document.getElementById('attendanceCourseList');
        const selectAllCheckbox = document.getElementById('toggleSelectAllCourses');
        const selectedCountEl = document.getElementById('attendanceSelectedCount');
        if (!listEl || !selectAllCheckbox || !selectedCountEl) return;

        const allVisibleCheckboxes = listEl.querySelectorAll('.attendance-course-item:not([style*="display: none"]) .form-check-input:not(:disabled)');
        const allVisibleChecked = listEl.querySelectorAll('.attendance-course-item:not([style*="display: none"]) .form-check-input:checked:not(:disabled)');

        const selected = allVisibleChecked.length;
        const totalVisible = allVisibleCheckboxes.length;
        
        selectedCountEl.textContent = `${selected} Selected`;

        if (totalVisible === 0) {
            selectAllCheckbox.checked = false;
            selectAllCheckbox.indeterminate = false;
            selectAllCheckbox.disabled = true;
        } else {
            selectAllCheckbox.disabled = false;
            if (selected === 0) {
                selectAllCheckbox.checked = false;
                selectAllCheckbox.indeterminate = false;
            } else if (selected === totalVisible) {
                selectAllCheckbox.checked = true;
                selectAllCheckbox.indeterminate = false;
            } else {
                selectAllCheckbox.checked = false;
                selectAllCheckbox.indeterminate = true;
            }
        }
      }
      
      

      // --- Handle modal stacking/blur visual effects ---
      function initModalZIndexHandlers() {
        // When Rename modal shows, blur Profile Manager
        renameProfileModalEl.addEventListener('show.bs.modal', function () {
            profileManagerModalEl.classList.add('blur-backdrop');
        });
        // When Rename modal hides, remove blur from Profile Manager
        renameProfileModalEl.addEventListener('hide.bs.modal', function () {
            profileManagerModalEl.classList.remove('blur-backdrop');
        });
        // When Confirmation modal shows, blur Profile Manager
        confirmationModalEl.addEventListener('show.bs.modal', function () {
            profileManagerModalEl.classList.add('blur-backdrop');
        });
        // When Confirmation modal hides, remove blur from Profile Manager
        confirmationModalEl.addEventListener('hide.bs.modal', function () {
            profileManagerModalEl.classList.remove('blur-backdrop');
        });
        // NEW: Blur main UI when attendance modal is open
        attendanceImportModalEl.addEventListener('show.bs.modal', function () {
            document.querySelector('.hero').style.filter = 'blur(4px)';
            document.querySelector('#Auto-Calculator').style.filter = 'blur(4px)';
        });
        attendanceImportModalEl.addEventListener('hide.bs.modal', function () {
            document.querySelector('.hero').style.filter = 'none';
            document.querySelector('#Auto-Calculator').style.filter = 'none';
        });
      }

      function migrateOldProfiles() {
          const oldProfilesData = localStorage.getItem('uafCalculatorProfiles');
          if (oldProfilesData) {
              try {
                  const oldProfiles = JSON.parse(oldProfilesData);
                  const newProfiles = getProfiles();
                  let migratedCount = 0;

                  Object.keys(oldProfiles).forEach(oldId => {
                      const oldProfile = oldProfiles[oldId];
                      const alreadyExists = Object.values(newProfiles).some(
                          p => p.studentInfo.registration === oldProfile.studentInfo.registration
                      );

                      if (!alreadyExists && oldProfile.studentInfo) {
                          const newProfile = {
                              ...oldProfile,
                              displayName: `${oldProfile.studentInfo.name} (${oldProfile.studentInfo.registration})`,
                              createdAt: new Date().toISOString(),
                              lastModified: new Date().toISOString()
                          };
                          const newId = `profile_${Date.now()}_${migratedCount}`;
                          newProfiles[newId] = newProfile;
                          migratedCount++;
                      }
                  });

                  if (migratedCount > 0) {
                      saveProfiles(newProfiles);
                      showToast(`${migratedCount} profile(s) from a previous version were successfully migrated!`, 'success');
                  }

                  localStorage.removeItem('uafCalculatorProfiles'); // Remove old data after migration
              } catch (e) {
                  console.error("Failed to migrate old profiles:", e);
              }
          }
      }

      function initScrollAnimations() {
        const observer = new IntersectionObserver((entries) => {
          entries.forEach(entry => {
            if (entry.isIntersecting) {
              entry.target.classList.add('is-visible');
              observer.unobserve(entry.target);
            }
          });
        }, { threshold: 0.1 });
        document.querySelectorAll('.fade-in-on-scroll').forEach(el => observer.observe(el));
      }

      function getProfiles() {
        return JSON.parse(localStorage.getItem('uafCalculatorProfiles_v2') || '{}');
      }

      function saveProfiles(profiles) {
        localStorage.setItem('uafCalculatorProfiles_v2', JSON.stringify(profiles));
      }

      function getActiveProfileId() {
        return localStorage.getItem('uafCalculatorActiveProfile_v2');
      }

      function setActiveProfileId(id) {
        localStorage.setItem('uafCalculatorActiveProfile_v2', id);
      }

      function getBackupInfo() {
          return JSON.parse(localStorage.getItem('uafCalculatorBackupInfo') || '{}');
      }

      function saveBackupInfo(info) {
          localStorage.setItem('uafCalculatorBackupInfo', JSON.stringify(info));
      }

      function loadProfiles() {
        try { // <<< ADDED TRY within loadProfiles for more specific error handling
          const profiles = getProfiles();
          const activeProfileId = getActiveProfileId();
          updateProfileSwitcher(profiles, activeProfileId);

          if (activeProfileId && profiles[activeProfileId]) {
            loadProfile(activeProfileId); // This calls calculateCGPA and displayCGPAResults
            addStatusMessage('Loaded active profile from session.', 'info');
          } else if (activeProfileId) {
            // Active ID exists but profile doesn't - clear the invalid ID
            setActiveProfileId('');
            addStatusMessage('Cleared invalid active profile ID from session.', 'warning');
          }
        } catch (error) { // <<< ADDED CATCH
          console.error("Failed to load profiles:", error);
          showToast("Error loading saved profiles. Data might be corrupted.", "error");
          // Clear potentially corrupted storage
          localStorage.removeItem('uafCalculatorProfiles_v2');
          localStorage.removeItem('uafCalculatorActiveProfile_v2');
          // Attempt to recover by resetting UI elements related to profiles
          try {
              updateProfileSwitcher({}, ''); // Clear switcher
              profileManagementDiv.style.display = 'none';
              if(resultContainer) resultContainer.style.display = 'none'; // Hide results if loading failed
          } catch (uiError) {
              console.error("Error resetting UI after profile load failure:", uiError);
          }
        }
      }

      function updateProfileSwitcher(profiles, activeProfileId) {
        const profileKeys = Object.keys(profiles);
        if (profileKeys.length > 0) {
          profileSwitcher.innerHTML = '<option value="">Select a saved profile...</option>';
          profileKeys.forEach(profileId => {
            const profile = profiles[profileId];
            if (profile && profile.studentInfo) {
                const option = document.createElement('option');
                option.value = profileId;
                option.textContent = profile.displayName || `${profile.studentInfo.name} (${profile.studentInfo.registration})`;
                if (profileId === activeProfileId) {
                  option.selected = true;
                }
                profileSwitcher.appendChild(option);
            }
          });
          profileManagementDiv.style.display = 'block';
        } else {
          profileManagementDiv.style.display = 'none';
        }
      }

      function loadProfile(profileId) {
        const profiles = getProfiles();
        if (profiles[profileId]) {
          processedData = profiles[profileId];
          isInitialLoad = true;

          bedModeActive = processedData.bedMode || false; // --- NEW: Load B.Ed. preference

          renderResults(processedData); // --- MODIFIED: Call new render function
          
          registrationNumber.value = processedData.studentInfo.registration;
          setActiveProfileId(profileId);
          updateProfileSwitcher(profiles, profileId);
        }
      }

      function switchProfile(event) {
        const profileId = event.target.value;
        if (profileId) {
          loadProfile(profileId);
          showToast(`Switched to profile: ${getProfiles()[profileId].displayName}`, 'info');
        }
      }

      function saveActiveProfile() {
        const activeProfileId = getActiveProfileId();
        if (activeProfileId && processedData) {
            const profiles = getProfiles();
            if (profiles[activeProfileId]) {
                processedData.lastModified = new Date().toISOString();
                profiles[activeProfileId] = processedData;
                saveProfiles(profiles);
            }
        }
      }

      function openRenameModal(profileId) {
        const profiles = getProfiles();
        if (!profileId || !profiles[profileId]) {
            showToast('Invalid profile selected for rename.', 'warning');
            return;
        }
        document.getElementById('newProfileName').value = profiles[profileId].displayName;
        saveProfileNameBtn.dataset.profileId = profileId; // Store the ID
        renameProfileModal.show();
      }

      function renameProfile() {
          const profileId = saveProfileNameBtn.dataset.profileId;
          const newName = document.getElementById('newProfileName').value.trim();

          if (!newName) {
              showToast('Profile name cannot be empty.', 'error');
              return;
          }

          const profiles = getProfiles();
          // FIX: Iterate over keys (profile IDs) to correctly check for duplicates 
          // while ensuring the current profile (profileId) is excluded.
          const nameExists = Object.keys(profiles).some(currentId => 
              profiles[currentId].displayName === newName && currentId !== profileId
          );
          
          if (nameExists) {
              showToast('A profile with this name already exists.', 'error');
              return;
          }

          profiles[profileId].displayName = newName;
          profiles[profileId].lastModified = new Date().toISOString();
          saveProfiles(profiles);
          renameProfileModal.hide();
          showToast('Profile renamed successfully!', 'success');

          updateProfileSwitcher(profiles, getActiveProfileId());
          if (profileManagerModalEl.classList.contains('show')) {
              renderProfileManager();
          }
      }

      function showConfirmationModal(title, body, onConfirm) {
        document.getElementById('confirmationModalTitle').textContent = title;
        document.getElementById('confirmationModalBody').textContent = body;
        confirmationCallback = onConfirm;
        confirmationModal.show();
      }

      function handleConfirm() {
        if (typeof confirmationCallback === 'function') {
          confirmationCallback();
        }
        confirmationModal.hide();
        confirmationCallback = null;
      }

      // --- PROFILE MANAGER FUNCTIONS ---

      // NEW CODE (replace with this)
      function renderProfileManager() {
        const profiles = getProfiles();
        const profileListEl = document.getElementById('profileManagerList');
        const profileCountStat = document.getElementById('profileCountStat');
        const lastBackupStat = document.getElementById('lastBackupStat');

        const profileKeys = Object.keys(profiles);
        profileCountStat.textContent = `${profileKeys.length} Profile${profileKeys.length !== 1 ? 's' : ''}`;

        const backupInfo = getBackupInfo();
        lastBackupStat.textContent = backupInfo.lastBackup ? `Last Backup: ${new Date(backupInfo.lastBackup).toLocaleString()}` : 'Last Backup: Never';

        if (profileKeys.length === 0) {
            profileListEl.innerHTML = '<li class="text-center text-muted p-4">No profiles saved yet.</li>';
            // Disable buttons if list is empty
            document.getElementById('bulkActionsBtn').disabled = true;
            document.getElementById('exportProfilesBtnModal').disabled = true;
            document.getElementById('selectAllProfiles').checked = false;
            document.getElementById('selectAllProfiles').indeterminate = false;
            return;
        }

        profileListEl.innerHTML = profileKeys.map(id => {
            const profile = profiles[id];
            const lastModified = profile.lastModified ? new Date(profile.lastModified).toLocaleString() : 'N/A';
            let detailsHtml = '';

            // Check if this is a B.Ed. profile
            if (profile.bedMode) {
                // B.Ed. Profile Visualization
                const bedSemesters = filterSemesters(profile.semesters, true);
                const bedData = { ...profile, semesters: bedSemesters };
                const bedCgpa = calculateCGPA(bedData);
                const bedSemesterCount = Object.keys(bedData.semesters).length;
                const bedCourseCount = Object.values(bedData.semesters).reduce((sum, s) => sum + s.courses.length, 0);

                const otherSemesters = filterSemesters(profile.semesters, false);
                const otherData = { ...profile, semesters: otherSemesters };
                const otherCgpa = calculateCGPA(otherData);
                const otherSemesterCount = Object.keys(otherData.semesters).length;
                const otherCourseCount = Object.values(otherData.semesters).reduce((sum, s) => sum + s.courses.length, 0);

                detailsHtml = `
                  <div class="profile-item-name">${profile.displayName} <span class="badge bg-primary-subtle text-primary-emphasis rounded-pill ms-2" style="font-size: 0.7em;">B.Ed. Profile</span></div>
                  <div class="profile-item-meta" style="grid-column: 1 / -1;"><i class="fa-solid fa-id-card"></i> ${profile.studentInfo.registration}</div>
                  
                  <!-- B.Ed. Details -->
                  <div class="profile-item-meta" style="grid-column: 1 / -1; margin-top: 5px; padding-top: 5px; border-top: 1px solid rgba(122, 106, 216, 0.1);">
                    <strong class="small" style="color: var(--brand);">B.Ed. Program:</strong>
                  </div>
                  <div class="profile-item-meta" style="padding-left: 15px;"><i class="fa-solid fa-graduation-cap"></i> CGPA: ${bedCgpa.cgpa.toFixed(4)}</div>
                  <div class="profile-item-meta" style="padding-left: 15px;"><i class="fa-solid fa-book"></i> ${bedSemesterCount} Sem, ${bedCourseCount} Crs</div>

                  <!-- Other Details -->
                  <div class="profile-item-meta" style="grid-column: 1 / -1; margin-top: 5px; padding-top: 5px; border-top: 1px solid rgba(122, 106, 216, 0.1);">
                    <strong class="small" style="color: var(--brand);">Other Program:</strong>
                  </div>
                  <div class="profile-item-meta" style="padding-left: 15px;"><i class="fa-solid fa-graduation-cap"></i> CGPA: ${otherCgpa.cgpa.toFixed(4)}</div>
                  <div class="profile-item-meta" style="padding-left: 15px;"><i class="fa-solid fa-book"></i> ${otherSemesterCount} Sem, ${otherCourseCount} Crs</div>
                  
                  <div class="profile-item-meta" style="grid-column: 1 / -1; margin-top: 5px; padding-top: 5px; border-top: 1px solid rgba(122, 106, 216, 0.1);">
                    <i class="fa-solid fa-clock"></i> ${lastModified}
                  </div>
                `;

            } else {
                // Standard Profile Visualization
                const cgpaData = calculateCGPA(profile);
                const semesterCount = Object.keys(profile.semesters).length;
                const courseCount = Object.values(profile.semesters).reduce((sum, s) => sum + s.courses.length, 0);
                
                detailsHtml = `
                  <div class="profile-item-name">${profile.displayName}</div>
                  <div class="profile-item-meta"><i class="fa-solid fa-id-card"></i> ${profile.studentInfo.registration}</div>
                  <div class="profile-item-meta"><i class="fa-solid fa-graduation-cap"></i> CGPA: ${cgpaData.cgpa.toFixed(4)}</div>
                  <div class="profile-item-meta"><i class="fa-solid fa-book"></i> ${semesterCount} Semesters, ${courseCount} Courses</div>
                  <div class="profile-item-meta"><i class="fa-solid fa-clock"></i> ${lastModified}</div>
                `;
            }

            return `
              <li class="profile-item" data-profile-id="${id}">
                  <input class="form-check-input profile-checkbox" type="checkbox" value="${id}">
                  <div class="profile-item-details" style="${profile.bedMode ? 'grid-template-columns: repeat(2, 1fr);' : ''}">
                      ${detailsHtml}
                  </div>
                  <div class="profile-item-actions">
                      <button class="btn btn-sm btn-soft rounded-pill action-load" title="Load Profile"><i class="fa-solid fa-arrow-up-right-from-square"></i></button>
                      <button class="btn btn-sm btn-soft rounded-pill action-rename" title="Rename"><i class="fa-solid fa-pen"></i></button>
                      <button class="btn btn-sm btn-soft rounded-pill text-danger action-delete" title="Delete"><i class="fa-solid fa-trash"></i></button>
                  </div>
              </li>
            `;
        }).join('');

        // --- Attach event listeners for quick actions ---
        profileListEl.querySelectorAll('.action-load').forEach(btn => btn.addEventListener('click', e => {
            loadProfile(e.currentTarget.closest('.profile-item').dataset.profileId);
            profileManagerModal.hide();
        }));
        profileListEl.querySelectorAll('.action-rename').forEach(btn => btn.addEventListener('click', e => {
            openRenameModal(e.currentTarget.closest('.profile-item').dataset.profileId);
        }));
        profileListEl.querySelectorAll('.action-delete').forEach(btn => btn.addEventListener('click', e => {
            const profileId = e.currentTarget.closest('.profile-item').dataset.profileId;
            const profileName = profiles[profileId]?.displayName || 'this profile';
            showConfirmationModal('Delete Profile?', `Are you sure you want to delete "${profileName}"?`, () => {
                deleteProfiles([profileId]);
            });
        }));

        // Reset bulk action buttons
        document.getElementById('bulkActionsBtn').disabled = true;
        document.getElementById('exportProfilesBtnModal').disabled = true;
        document.getElementById('selectAllProfiles').checked = false;
        document.getElementById('selectAllProfiles').indeterminate = false;
      }

      function handleBulkAction() {
          const selectedIds = Array.from(document.querySelectorAll('.profile-checkbox:checked')).map(cb => cb.value);
          if (selectedIds.length === 0) {
              showToast('No profiles selected.', 'warning');
              return;
          }
          showConfirmationModal(`Delete ${selectedIds.length} Profiles?`, `This will permanently delete the selected profiles.`, () => {
              deleteProfiles(selectedIds);
          });
      }

      function deleteProfiles(idsToDelete) {
          const profiles = getProfiles();
          let deletedCount = 0;
          idsToDelete.forEach(id => {
              if (profiles[id]) {
                  delete profiles[id];
                  deletedCount++;
                  if (getActiveProfileId() === id) {
                      setActiveProfileId('');
                  }
              }
          });
          saveProfiles(profiles);
          showToast(`Successfully deleted ${deletedCount} profile(s).`, 'success');
          renderProfileManager();
          updateProfileSwitcher(profiles, getActiveProfileId());
          if (!getActiveProfileId()) {
              resultContainer.style.display = 'none';
              document.getElementById('bedResultContainer').style.display = 'none'; // Hide B.Ed. container
              registrationNumber.value = '';
          }
      }

      function exportSelectedProfiles() {
          const selectedIds = Array.from(document.querySelectorAll('#profileManagerList .profile-checkbox:checked')).map(cb => cb.value);
          const profiles = getProfiles();
          const profilesToExport = {};
          let exportCount = 0;
          let filename = `uaf-cgpa-profiles-backup-${new Date().toISOString().split('T')[0]}.json`; // Default filename

          if (selectedIds.length === 0) {
              showToast('No profiles selected to export. Please select profiles from the list.', 'warning');
              return;
          }

          selectedIds.forEach(id => {
              if (profiles[id]) {
                  profilesToExport[id] = profiles[id];
                  exportCount++;
              }
          });

          // Custom filename for single profile export
          if (exportCount === 1) {
              const singleProfileId = selectedIds[0];
              
              // --- THIS BLOCK IS FIXED ---
              // Safely check for displayName and provide a fallback.
              let profileName = 'profile'; // Default name
              if (profiles[singleProfileId].displayName) {
                  profileName = profiles[singleProfileId].displayName.replace(/[^a-z0-9]/gi, '_').toLowerCase();
              // Next, I'll search for the importProfiles function, which is what these buttons should call.
              } else if (profiles[singleProfileId].studentInfo && profiles[singleProfileId].studentInfo.registration) {
                  // Fallback to registration number if no display name
                  profileName = profiles[singleProfileId].studentInfo.registration.replace(/[^a-z0-9]/gi, '_').toLowerCase();
              // EUREKA!
              }
              
              filename = `${profileName}-profile-backup.json`;
          }

          const backupData = {
              version: '2.0.0',
              exportDate: new Date().toISOString(),
              profiles: profilesToExport
          };

          const blob = new Blob([JSON.stringify(backupData, null, 2)], { type: 'application/json' });
          const url = URL.createObjectURL(blob);
          const a = document.createElement('a');
          a.href = url;
          a.download = filename; // Use the determined filename
          document.body.appendChild(a);
          a.click();
          a.remove();
          URL.revokeObjectURL(url);

          saveBackupInfo({ lastBackup: new Date().toISOString() });
          showToast(`${exportCount} profile(s) exported.`, 'success');
          renderProfileManager(); // Update last backup date
      }


      function importProfiles() {
          const input = document.createElement('input');
          input.type = 'file';
          input.accept = '.json';
          input.onchange = e => {
              const file = e.target.files[0];
              if (!file) return;
              const reader = new FileReader();
              reader.onload = event => {
                  try {
                      const importedData = JSON.parse(event.target.result);
                      
                      if (!importedData.profiles || importedData.version !== '2.0.0') {
                          throw new Error('Invalid or incompatible backup file.');
                      }

                      const existingProfiles = getProfiles();
                      let importedCount = 0, skippedCount = 0;

                      Object.keys(importedData.profiles).forEach(id => {
                          if (existingProfiles[id]) {
                              skippedCount++;
                          } else {
                              existingProfiles[id] = importedData.profiles[id];
                              importedCount++;
                          }
                      });

                      saveProfiles(existingProfiles);
                      showToast(`Import complete: ${importedCount} added, ${skippedCount} skipped.`, 'success');
                      loadProfiles(); // Reload profiles into switcher
                      if (profileManagerModalEl.classList.contains('show')) {
                        renderProfileManager(); // Re-render manager if open
                      }

                  } catch (error) {
                      showToast(`Import failed: ${error.message}`, 'error');
                      console.error('Import error:', error);
                  }
              };

              // --- FIX: Add onerror handler for file read errors ---
              reader.onerror = event => {
                  showToast('Failed to read the file. Please check the file and try again.', 'error');
                  console.error('FileReader error:', event.target.error);
              };
              // --- End of Fix ---

              reader.readAsText(file);
          };
          input.click();
      }

      // --- END OF PROFILE MANAGER FUNCTIONS ---

      function updateTotalsDisplay() {
        const cgpaData = calculateCGPA(processedData);
        if (!cgpaData) return;

        studentName.innerHTML = `<i class="fa-solid fa-user-graduate me-2"></i>${processedData.studentInfo.name}`;
        studentReg.textContent = processedData.studentInfo.registration;
        totalCgpa.textContent = formatNumber(cgpaData.cgpa).toFixed(4);
        totalPercentage.textContent = `${formatNumber(cgpaData.percentage, 2).toFixed(2)}%`;
        totalMarksObtained.textContent = cgpaData.totalMarksObtained.toFixed(0);
        totalMaxMarks.textContent = `/ ${cgpaData.totalMaxMarks.toFixed(0)}`;

        renderGpaChart();
        saveActiveProfile();
      }

      function initBackToTop() {
        window.addEventListener('scroll', () => backToTopButton.classList.toggle('visible', window.pageYOffset > 300));
        backToTopButton.addEventListener('click', () => window.scrollTo({ top: 0, behavior: 'smooth' }));
      }

      function createToastContainer() {
        if (!document.getElementById('toast-container')) {
          const toastContainer = document.createElement('div');
          toastContainer.id = 'toast-container';
          document.body.appendChild(toastContainer);
        }
      }

      function showToast(message, type = 'success') {
        const toastContainer = document.getElementById('toast-container');
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        const icons = { success: 'fa-circle-check', error: 'fa-circle-exclamation', warning: 'fa-triangle-exclamation', info: 'fa-circle-info' };
        toast.innerHTML = `<div class="toast-content"><i class="toast-icon fa-solid ${icons[type]}"></i><span class="toast-message">${message}</span></div><div class="toast-progress"></div>`;
        toastContainer.appendChild(toast);
        setTimeout(() => toast.classList.add('show'), 10);
        setTimeout(() => {
          toast.classList.remove('show');
          setTimeout(() => toast.remove(), 300);
        }, 3000);
      }

      function initCustomCursor() {
        document.addEventListener('mousemove', (e) => {
          cursorDot.style.display = window.innerWidth > 768 ? 'block' : 'none';
          cursorDot.style.left = `${e.clientX}px`;
          cursorDot.style.top = `${e.clientY}px`;
        });
      }

      // NEW initTheme function
function initTheme() {
  const THEME_KEY = 'uaf-theme';
  
  // Find BOTH the new mobile input and the new desktop button
  const themeToggleInput = document.getElementById('themeToggleInput');
  const themeToggleBtn = document.getElementById('themeToggleBtn');

  const applyTheme = (theme) => {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem(THEME_KEY, theme);
    
    const isDark = theme === 'dark';
    
    // 1. Set the state of the mobile toggle
    if (themeToggleInput) {
        themeToggleInput.checked = isDark;
    }
    
    // 2. Set the icon for the desktop button
    if (themeToggleBtn) {
        const iconClass = isDark ? 'fa-solid fa-sun' : 'fa-solid fa-moon';
        themeToggleBtn.innerHTML = `<i class="${iconClass}"></i>`;
    }
  };

  // Get the current theme and apply it
  const currentTheme = localStorage.getItem(THEME_KEY) || 'light'; // <--- THIS IS THE CHANGE
  applyTheme(currentTheme);

  // Function to handle the toggle logic
  const toggleLogic = () => {
    const newTheme = document.documentElement.getAttribute('data-theme') === 'light' ? 'dark' : 'light';
    applyTheme(newTheme);
  };

  // Add event listeners to BOTH elements
  if (themeToggleInput) {
    themeToggleInput.addEventListener('change', toggleLogic); // Use 'change' for checkboxes
  }
  if (themeToggleBtn) {
    themeToggleBtn.addEventListener('click', toggleLogic); // Use 'click' for the button
  }
}

      function initContactForm() {
        contactForm.addEventListener('submit', async (e) => {
          e.preventDefault();
          if (!contactForm.checkValidity()) {
            e.stopPropagation();
            contactForm.classList.add('was-validated');
            return;
          }
          const data = new FormData(contactForm);
          const statusEl = document.getElementById('contact-form-status');
          try {
            const res = await fetch(contactForm.action, { method: 'POST', body: data, headers: { 'Accept': 'application/json' } });
            if (res.ok) {
              statusEl.textContent = "Thanks! We'll get back to you soon.";
              statusEl.className = "text-success small";
              contactForm.reset();
              contactForm.classList.remove('was-validated');
              showToast('Message sent successfully!', 'success');
            } else {
              throw new Error('Form submission failed');
            }
          } catch {
            statusEl.textContent = "Oops! There was a problem. Please try again.";
            statusEl.className = "text-danger small";
            showToast('Failed to send message.', 'error');
          }
        });
      }

      function addStatusMessage(message, type = 'info') {
        const timestamp = new Date().toLocaleTimeString();
        allLogs.push({ timestamp, message, type });
        const messageEl = document.createElement('div');
        messageEl.className = `status-line status-${type}`;
        messageEl.textContent = `[${timestamp}] ${message}`;
        statusLog.prepend(messageEl);
        statusLog.scrollTop = 0;
      }

      function showLoadingStage(stage) {
        ['connecting', 'fetching', 'processing', 'complete'].forEach(s => {
          const el = document.getElementById(`${s}Stage`);
          if (el) el.style.display = 'none';
        });
        if (stage) {
            const el = document.getElementById(`${stage}Stage`);
            if (el) el.style.display = 'block';
        }
        loadingContainer.style.display = stage ? 'block' : 'none';
      }

      function downloadLog() {
        addStatusMessage('Preparing log file for download...', 'info');
        let logContent = "UAF CGPA Calculator - M SAQLAIN - Activity Log\n============================================\n\n";
        allLogs.forEach(log => logContent += `[${log.timestamp}] ${log.message}\n`);
        const blob = new Blob([logContent], { type: 'text/plain' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `cgpa_calculator_log_${new Date().toISOString().replace(/[:.]/g, '-')}.txt`;
        document.body.appendChild(a);
        a.click();
        a.remove();
        URL.revokeObjectURL(url);
        addStatusMessage('Log file downloaded successfully', 'success');
        showToast('Log file downloaded!', 'success');
      }

      function clearLog() {
        statusLog.innerHTML = '';
        allLogs = [];
        addStatusMessage('Log cleared', 'info');
        showToast('Log cleared', 'info');
      }

      // --- 
      // --- UPDATED processSemesterName Function ---
      // --- 
      // ---
      // --- UPDATED processSemesterName Function ---
      // ---
      function processSemesterName(semester) {
          if (!semester) return 'Unknown Semester';

          const semesterLower = semester.toLowerCase();

          // Regex to match "YYYY-YY" or "YYYY-YYYY"
          const yearRangeMatch = semesterLower.match(/(\d{4})-(\d{2,4})/);
          // Regex to match a single 4-digit year
          const singleYearMatch = semesterLower.match(/\b(\d{4})\b/);

          let season = 'Unknown';
          let year = '';

          if (semesterLower.includes('spring')) {
              season = 'Spring';
              if (yearRangeMatch) {
                  year = yearRangeMatch[2]; // "25" or "2025"
                  // Ensure it's a 4-digit year
                  if (year.length === 2) {
                      year = `20${year}`; // "25" -> "2025"
                  }
              } else if (singleYearMatch) {
                  // If only a single year is present for Spring, assume it's the latter year
                  year = (parseInt(singleYearMatch[1]) + 1).toString();
              }
          } else if (semesterLower.includes('winter')) {
              season = 'Winter';
              if (yearRangeMatch) {
                  year = yearRangeMatch[1]; // "2024"
              } else if (singleYearMatch) {
                  year = singleYearMatch[1];
              }
          } else if (semesterLower.includes('summer')) {
              season = 'Summer';
              // Summer usually belongs to the first year of the range or the single year mentioned
              if (yearRangeMatch) {
                  year = yearRangeMatch[1]; // "2024"
              } else if (singleYearMatch) {
                  year = singleYearMatch[1];
              }
          } else if (semesterLower.includes('fall')) {
              season = 'Fall';
              // Fall usually belongs to the first year of the range or the single year mentioned
              if (yearRangeMatch) {
                  year = yearRangeMatch[1]; // "2024"
              } else if (singleYearMatch) {
                  year = singleYearMatch[1];
              }
          }

          // If a season and year were found, return them
          if (season !== 'Unknown' && year) {
              return `${season} ${year}`;
          }

          // Fallback logic for non-standard formats like "Winter20", "Spring24" etc. from attendance
          // Converts "SeasonYY" directly to "Season 20YY"
          const attendanceMatch = semesterLower.match(/^(winter|spring|summer|fall)(\d{2})$/);
          if (attendanceMatch) {
              const season = attendanceMatch[1].charAt(0).toUpperCase() + attendanceMatch[1].slice(1); // Capitalize season
              const yearYY = attendanceMatch[2];
              return `${season} 20${yearYY}`; // e.g., Spring 2024
          }

          // Default fallback (original string, capitalized) if no other pattern matches
          return semester.charAt(0).toUpperCase() + semester.slice(1);
      }

      function getSemesterOrderKey(processedSemesterName) {
        // Takes the processed name like "Winter 2020" or "Spring 2021"
        if (!processedSemesterName) return '9999-9'; // Ensure unknowns sort last

        const semesterLower = processedSemesterName.toLowerCase();

        // Handle Forecast semesters - place them far in the future
        if (semesterLower.startsWith('forecast')) {
            const num = parseInt(semesterLower.split(' ')[1] || '1');
            // Ensure proper numerical sorting for multiple forecasts
            return `3000-${num.toString().padStart(2, '0')}`;
        }

        let year = 0;
        let seasonOrder = 9; // Default for unknowns

        const yearMatch = semesterLower.match(/\b(\d{4})\b/); // Match the 4-digit year
        if (yearMatch) {
            year = parseInt(yearMatch[1]);
        } else {
            return '9999-9'; // Cannot determine year, sort last
        }

        let academicYearStart = year;

        // Determine season order and adjust academic year start for Spring/Summer
        if (semesterLower.includes('winter')) {
            seasonOrder = 1;
            academicYearStart = year; // Winter 2020 belongs to AY starting 2020
        } else if (semesterLower.includes('spring')) {
            seasonOrder = 2;
            academicYearStart = year - 1; // Spring 2021 belongs to AY starting 2020
        } else if (semesterLower.includes('summer')) {
            seasonOrder = 3;
            academicYearStart = year - 1; // Summer 2021 belongs to AY starting 2020
        } else if (semesterLower.includes('fall')) {
             // Assuming Fall starts the *next* academic cycle relative to Summer
             // Fall 2021 would belong to AY starting 2021
            seasonOrder = 4;
            academicYearStart = year;
        } else {
             seasonOrder = 9; // Unknown season type
             academicYearStart = year;
        }

        // Format: YYYY-S (e.g., 2020-1, 2020-2, 2020-3, 2021-1)
        return `${academicYearStart}-${seasonOrder}`;
      }

      function processScrapedData(data) {
        if (!data || !data.resultData) return null;
        const studentInfo = { name: data.resultData[0]?.StudentName || '', registration: data.resultData[0]?.RegistrationNo || '' };
        const semesters = {};
        const courseHistory = {};
        
        let hasBedCourses = false; // --- NEW B.Ed. Flag ---

        data.resultData.forEach(course => {
          const originalSemester = course.Semester || 'Unknown Semester';
          const semesterName = processSemesterName(originalSemester);
          const courseCode = (course.CourseCode || '').trim().toUpperCase();
          const historyKey = courseCode;

          // --- NEW B.Ed. Check ---
          const isBedCourse = BED_COURSES.has(courseCode); // <-- MODIFIED: Store this check
          if (isBedCourse) {
            hasBedCourses = true;
          }
          // --- End of NEW B.Ed. Check ---

          if (!semesters[semesterName]) {
            // Pass the *processed* semesterName to getSemesterOrderKey
            semesters[semesterName] = { 
              originalName: originalSemester, 
              sortKey: getSemesterOrderKey(semesterName), 
              courses: [],
              hasBedCourses: false,    // <-- ADD THIS
              hasOtherCourses: false   // <-- ADD THIS
            };
          }

          // --- ADD THIS BLOCK ---
          // Tag the semester with the type of course it contains
          if (isBedCourse) {
            semesters[semesterName].hasBedCourses = true;
          } else {
            semesters[semesterName].hasOtherCourses = true;
          }
          // --- END ADDED BLOCK ---

          const creditHoursStr = course.CreditHours || '0';
          const creditHours = parseInt(creditHoursStr.match(/\d+/)?.[0] || '0');
          const marks = parseFloat(course.Total || '0');

          // Pass the grade to the QP calculation
          let qualityPoints = calculateQualityPoints(marks, creditHours, course.Grade);

          // This 'if' block is now redundant if 'F' is handled in calculateQualityPoints,
          // but we can leave it as a safeguard.
          if (course.Grade === 'F') {
            qualityPoints = 0;
          }

          // --- 
          // --- UPDATED courseData Object ---
          // --- 
          const courseData = {
            code: courseCode,
            title: course.CourseTitle || '',
            creditHours: creditHours,
            creditHoursDisplay: creditHoursStr,
            marks: marks,
            qualityPoints: qualityPoints,
            grade: course.Grade || '',
            teacher: course.TeacherName || '',
            mid: course.Mid || '0',
            assignment: course.Assignment || '0',
            final: course.Final || '0',
            practical: course.Practical || '0',
            isExtraEnrolled: false,
            isRepeated: false,
            isDeleted: false,
            isCustom: false,
            originalSemester: originalSemester // <-- THIS LINE WAS ADDED
          };

          if (!courseHistory[historyKey]) {
            courseHistory[historyKey] = [];
          }
          courseHistory[historyKey].push({ semester: semesterName, semesterSortKey: getSemesterOrderKey(semesterName), marks: marks, data: courseData });
          semesters[semesterName].courses.push(courseData);
        });

        Object.values(courseHistory).forEach(history => {
          if (history.length > 1) {
            history.sort((a, b) => a.semesterSortKey.localeCompare(b.semesterSortKey));

            const passedCourses = history.filter(item => item.data.grade !== 'F');
            let bestAttempt;

            if (passedCourses.length > 0) {
              bestAttempt = passedCourses.reduce((prev, current) => (prev.marks > current.marks) ? prev : current);
            } else {
              bestAttempt = history.reduce((prev, current) => (prev.marks > current.marks) ? prev : current);
            }

            history.forEach(item => {
              item.data.isRepeated = true;
              if (item !== bestAttempt) {
                item.data.isExtraEnrolled = true;
              } else {
                item.data.isExtraEnrolled = false;
              }
            });
          }
        });

        // --- NEW: Return the flag ---
        return { studentInfo, semesters, courseHistory, hasBedCourses };
      }

      function calculateQualityPoints(marks, creditHours, grade) {
        marks = parseFloat(marks);
        creditHours = parseInt(creditHours);
        
        // Handle P/F grades first (Request 2)
        grade = (grade || '').trim().toUpperCase();
        if (grade === 'P') {
            return parseFloat(creditHours) * 4.0;
        }
        if (grade === 'F') {
            return 0;
        }

        // Keep existing marks-based logic as a fallback
        let qualityPoints = 0;
        if (creditHours === 10) {
            if (marks >= 160) qualityPoints = 40;
            else if (marks >= 100) qualityPoints = 40 - ((160 - marks) * 0.33333);
            else if (marks < 100) qualityPoints = 20 - ((100 - marks) * 0.5);
            if (marks < 80) qualityPoints = 0;
        } else if (creditHours === 9) {
            if (marks >= 144) qualityPoints = 36;
            else if (marks >= 90) qualityPoints = 36 - ((144 - marks) * 0.33333);
            else if (marks < 90) qualityPoints = 18 - ((90 - marks) * 0.5);
            if (marks < 72) qualityPoints = 0;
        } else if (creditHours === 8) {
            if (marks >= 128) qualityPoints = 32;
            else if (marks >= 80) qualityPoints = 32 - ((128 - marks) * 0.33333);
            else if (marks < 80) qualityPoints = 16 - ((80 - marks) * 0.5);
            if (marks < 64) qualityPoints = 0;
        } else if (creditHours === 7) {
            if (marks >= 112) qualityPoints = 28;
            else if (marks >= 70) qualityPoints = 28 - ((112 - marks) * 0.33333);
            else if (marks < 70) qualityPoints = 14 - ((70 - marks) * 0.5);
            if (marks < 56) qualityPoints = 0;
        } else if (creditHours === 6) {
            if (marks >= 96) qualityPoints = 24;
            else if (marks >= 60) qualityPoints = 24 - ((96 - marks) * 0.33333);
            else if (marks < 60) qualityPoints = 12 - ((60 - marks) * 0.5);
            if (marks < 48) qualityPoints = 0;
        } else if (creditHours === 5) {
            if (marks >= 80) qualityPoints = 20;
            else if (marks >= 50) qualityPoints = 20 - ((80 - marks) * 0.33333);
            else if (marks < 50) qualityPoints = 10 - ((50 - marks) * 0.5);
            if (marks < 40) qualityPoints = 0;
        } else if (creditHours === 4) {
            if (marks >= 64) qualityPoints = 16;
            else if (marks >= 40) qualityPoints = 16 - ((64 - marks) * 0.33333);
            else if (marks < 40) qualityPoints = 8 - ((40 - marks) * 0.5);
            if (marks < 32) qualityPoints = 0;
        } else if (creditHours === 3) {
            if (marks >= 48) qualityPoints = 12;
            else if (marks >= 30) qualityPoints = 12 - ((48 - marks) * 0.33333);
            else if (marks < 30) qualityPoints = 6 - ((30 - marks) * 0.5);
            if (marks < 24) qualityPoints = 0;
        } else if (creditHours === 2) {
            if (marks >= 32) qualityPoints = 8;
            else if (marks >= 20) qualityPoints = 8 - ((32 - marks) * 0.33333);
            else if (marks < 20) qualityPoints = 4 - ((20 - marks) * 0.5);
            if (marks < 16) qualityPoints = 0;
        } else if (creditHours === 1) {
            if (marks >= 16) qualityPoints = 4;
            else if (marks >= 10) qualityPoints = 4 - ((16 - marks) * 0.33333);
            else if (marks < 10) qualityPoints = 2 - ((10 - marks) * 0.5);
            if (marks < 8) qualityPoints = 0;
        }
        return parseFloat(Math.max(0, qualityPoints).toFixed(2));
      }

      function calculateCustomGrade(marks, creditHours) {
        const grading = { 10: { A: 160, B: 130, C: 100, D: 80 }, 9: { A: 144, B: 117, C: 90, D: 72 }, 8: { A: 128, B: 104, C: 80, D: 64 }, 7: { A: 112, B: 91, C: 70, D: 56 }, 6: { A: 96, B: 78, C: 60, D: 48 }, 5: { A: 80, B: 65, C: 50, D: 40 }, 4: { A: 64, B: 52, C: 40, D: 32 }, 3: { A: 48, B: 39, C: 30, D: 24 }, 2: { A: 32, B: 26, C: 20, D: 16 }, 1: { A: 16, B: 13, C: 10, D: 8 } };
        const scale = grading[creditHours];
        if (!scale) return 'F';
        if (marks >= scale.A) return 'A'; if (marks >= scale.B) return 'B';
        if (scale.C && marks >= scale.C) return 'C'; if (marks >= scale.D) return 'D';
        return 'F';
      }

      function calculateCGPA(data) {
        if (!data) return null;
        let totalQualityPoints = 0, totalCreditHours = 0, totalMarksObtained = 0, totalMaxMarks = 0;
        
        // Re-evaluate course history for repeated courses *every time* we calculate
        const courseHistory = {};
        Object.entries(data.semesters).forEach(([semesterName, semester]) => {
            semester.courses.forEach(course => {
                if (course.isDeleted) return; // Skip deleted courses entirely
                
                const historyKey = course.code.toUpperCase().trim();
                if (!courseHistory[historyKey]) {
                    courseHistory[historyKey] = [];
                }
                courseHistory[historyKey].push({
                    semester: semesterName,
                    semesterSortKey: semester.sortKey,
                    marks: course.marks,
                    data: course // Direct reference to the course object
                });
            });
        });

        // Reset all 'isExtraEnrolled' flags
        Object.values(courseHistory).flat().forEach(item => item.data.isExtraEnrolled = false);

        // Set 'isExtraEnrolled' flags based on current data
        Object.values(courseHistory).forEach(history => {
            if (history.length > 1) {
                history.sort((a, b) => a.semesterSortKey.localeCompare(b.semesterSortKey));
                const passedCourses = history.filter(item => item.data.grade !== 'F');
                let bestAttempt;

                if (passedCourses.length > 0) {
                    bestAttempt = passedCourses.reduce((prev, current) => (prev.marks > current.marks) ? prev : current);
                } else { // All attempts are 'F'
                    bestAttempt = history.reduce((prev, current) => (prev.marks > current.marks) ? prev : current);
                }

                history.forEach(item => {
                    item.data.isRepeated = true; // Mark all as repeated
                    if (item !== bestAttempt) {
                        item.data.isExtraEnrolled = true; // Mark non-best attempts
                    }
                });
            } else if (history.length === 1) {
                 history[0].data.isRepeated = false; // Not repeated if only one instance
            }
        });


        // Now calculate totals
        Object.values(data.semesters).forEach(semester => {
            semester.totalQualityPoints = 0;
            semester.totalCreditHours = 0;
            semester.totalMarksObtained = 0;
            semester.totalMaxMarks = 0;
            semester.courses.forEach(course => {
                if (!course.isExtraEnrolled && !course.isDeleted) {
                    semester.totalQualityPoints += course.qualityPoints;
                    semester.totalCreditHours += course.creditHours;
                    semester.totalMarksObtained += course.marks;

                    let maxMarks;
                    if ((course.grade || '').trim().toUpperCase() === 'P') {
                        // Assume 'P' grade courses with 1CH have 100 max marks, as requested
                        if (course.creditHours === 1) {
                            maxMarks = 100;
                        } else {
                            // Fallback for 'P' grade on other CH (if it ever happens)
                            // We assume the total marks obtained are the max marks for percentage
                            maxMarks = course.marks; 
                        }
                    } else {
                         maxMarks = { 10: 200, 9: 180, 8: 160, 7: 140, 6: 120, 5: 100, 4: 80, 3: 60, 2: 40, 1: 20 }[course.creditHours] || 0;
                    }

                    semester.totalMaxMarks += maxMarks;

                    totalQualityPoints += course.qualityPoints;
                    totalCreditHours += course.creditHours;
                    totalMarksObtained += course.marks;
                    totalMaxMarks += maxMarks;
                }
            });
            semester.gpa = semester.totalCreditHours > 0 ? (semester.totalQualityPoints / semester.totalCreditHours) : 0;
            semester.percentage = semester.totalMaxMarks > 0 ? (semester.totalMarksObtained / semester.totalMaxMarks * 100) : 0;
        });

        const cgpa = totalCreditHours > 0 ? (totalQualityPoints / totalCreditHours) : 0;
        const percentage = totalMaxMarks > 0 ? (totalMarksObtained / totalMaxMarks * 100) : 0;
        return { cgpa, percentage, totalQualityPoints, totalCreditHours, totalMarksObtained, totalMaxMarks };
      }

      function formatNumber(value, places = 4) { return parseFloat(value.toFixed(places)); }

      // --- NEW Function: Renders semester cards into a specific container ---
      function displaySemesterCards(containerId, data) {
        const container = document.getElementById(containerId);
        if (!container) return;

        container.innerHTML = '';
        Object.keys(data.semesters).sort((a,b) => data.semesters[a].sortKey.localeCompare(data.semesters[b].sortKey)).forEach(semesterName => {
          const semester = data.semesters[semesterName];
          
          // --- FIX ---
          // Safety check: Don't render a semester if its course list is missing.
          // We no longer hide empty non-forecast semesters, as this fixes the drag-and-drop bug.
          if (!semester.courses) {
              return;
          }
          // Check if it's a forecast semester (still needed for other logic)
          const isForecastSemester = semester.isForecast === true;
          // --- END FIX ---
          
          const semesterCard = document.createElement('div');
          
          semesterCard.dataset.semester = semesterName;

          const animationClass = isInitialLoad ? 'fade-in-on-scroll' : 'is-visible';
          semesterCard.className = `semester-card ${animationClass}`;

          semesterCard.dataset.semester = semesterName;
          
          const isForecastOrCustom = semesterName.toLowerCase().startsWith('forecast') || 
                                     !Object.values(processedData.courseHistory).flat().some(c => c.semester === semesterName && !c.data.isCustom);
          
          semesterCard.innerHTML = `
            <i class="fa-solid fa-trash delete-semester" title="Delete this semester" data-semester="${semesterName}"></i>
            <div class="d-flex align-items-center justify-content-between mb-3">
              <h5 class="mb-0 d-flex align-items-center">
                <i class="fa-solid fa-book-open me-2" style="color: var(--brand);"></i>
                <span id="semester-name-${semester.sortKey}">${semesterName}</span>
                
                ${isForecastOrCustom ? `<i class="fa-solid fa-pencil edit-semester-name" title="Rename semester" data-semester="${semesterName}" style="cursor: pointer; margin-left: 10px; font-size: 0.9em; color: var(--muted);"></i>` : ''}
                </h5>
              <div class="text-end" style="margin-right: 40px;">
                <p class="mb-0 text-body-secondary small">GPA:</p>
                <p class="mb-0 h4 fw-bold" style="color: var(--brand);">${formatNumber(semester.gpa).toFixed(4)}</p>
                <p class="mb-0 text-body-secondary small">${formatNumber(semester.percentage, 2).toFixed(2)}%</p>
              </div>
            </div>
            <button class="custom-course-btn" data-semester="${semesterName}"><i class="fa-solid fa-plus"></i> Custom Course</button>
            <div class="table-responsive"><table class="course-table"><thead><tr><th>Course</th><th>Hrs</th><th>Marks</th><th>Grade</th><th>Action</th></tr></thead>
              <tbody>${semester.courses.map((course, index) => {
                  const courseIdentifier = `${semesterName}-${course.code}-${course.total}-${index}`;
                  const courseTitle = course.title || (course.isCustom ? 'Custom Course' : 'N/A');
                  return `
                  <tr data-course-identifier="${courseIdentifier}" draggable="true" class="${course.isExtraEnrolled ? 'table-warning' : ''} ${course.isDeleted ? 'table-danger text-decoration-line-through' : ''} ${course.isCustom ? 'table-info' : ''}">
                    <td>
                      <div class="course-code-container">
                        <span class="fw-medium course-code clickable-info" data-course='${JSON.stringify(course).replace(/'/g, "&#39;")}'>
                          ${course.code}
                          <i class="fa-solid fa-info-circle ms-1 clickable-info small" data-course='${JSON.stringify(course).replace(/'/g, "&#39;")}' title="${courseTitle}"></i>
                        </span>
                        ${course.isExtraEnrolled ? '<sup class="extra-enrolled">Rep.</sup>' : ''}
                        ${course.isCustom && course.source === 'attendance' ? '<sup class="extra-enrolled" style="color: #087990; background-color: #cff4fc;">Atnd.</sup>' : ''}
                        ${course.isCustom && course.source !== 'attendance' ? '<span class="extra-enrolled">Custom</span>' : ''}
                      </div>
                    </td>
                    <td>${course.creditHoursDisplay || course.creditHours}</td><td>${course.marks}</td>
                    <td><span class="grade-badge grade-${course.grade}">${course.grade}</span></td>
                    <td class="course-actions">${course.isDeleted ? `<i class="fa-solid fa-rotate-left restore-course" data-course='${JSON.stringify(course).replace(/'/g, "&#39;")}' data-semester="${semesterName}" title="Restore"></i>` : `<i class="fa-solid fa-trash delete-course" data-course='${JSON.stringify(course).replace(/'/g, "&#39;")}' data-semester="${semesterName}" title="Delete"></i>`}</td>
                  </tr>`;
              }).join('')}</tbody>
            </table></div>`;
          container.appendChild(semesterCard);
        });

        isInitialLoad = false;
        // Note: We call attachResultEventListeners() *after* this function finishes
      }

      function displayCGPAResults(data, cgpaData) {
        processedData = data;
        resultContainer.style.display = 'block';

        // 1. Update the main CGPA card
        studentName.innerHTML = `<i class="fa-solid fa-user-graduate me-2"></i>${data.studentInfo.name}`;
        studentReg.textContent = data.studentInfo.registration;
        totalCgpa.textContent = formatNumber(cgpaData.cgpa).toFixed(4);
        totalPercentage.textContent = `${formatNumber(cgpaData.percentage, 2).toFixed(2)}%`;
        totalMarksObtained.textContent = cgpaData.totalMarksObtained.toFixed(0);
        totalMaxMarks.textContent = `/ ${cgpaData.totalMaxMarks.toFixed(0)}`;

        const cgpaCircle = document.getElementById('cgpaCircle');
        if(cgpaCircle) {
            const cgpa = parseFloat(totalCgpa.textContent);
            const percentage = (cgpa / 4.0) * 100;
            setTimeout(() => {
                cgpaCircle.style.strokeDasharray = `${percentage}, 100`;
            }, 100);
        }

        // 2. Render the semester cards into the *standard* container
        displaySemesterCards('semesterResults', data);

        // 3. Attach listeners
        attachResultEventListeners();

        // 4. Render chart and setup buttons
        renderGpaChart();
        
        const hasAttendanceCourses = Object.values(data.semesters).some(s => s.courses.some(c => c.isCustom && c.source === 'attendance'));
        if (!hasAttendanceCourses) {
             importedAttendanceCourses = [];
        }
        importedAttendanceCourses = [];
        setupAttendanceButton();
      }

      // --- NEW Function: Renders the B.Ed. tabbed interface ---
      function displayBedResults(data) {
        processedData = data; // *** FIX: Set global processedData, just like displayCGPAResults does ***
        // 1. Filter for B.Ed. results
        const bedSemesters = filterSemesters(data.semesters, true);
        const bedData = { ...data, semesters: bedSemesters };
        const bedCgpa = calculateCGPA(bedData);

        // 2. Filter for "Other" results
        const otherSemesters = filterSemesters(data.semesters, false);
        const otherData = { ...data, semesters: otherSemesters };
        const otherCgpa = calculateCGPA(otherData);

        // --- NEW: Populate Student Info Headers (Fixes Bug) ---
        document.getElementById('bed-studentName').innerHTML = `<i class="fa-solid fa-user-graduate me-2"></i>${data.studentInfo.name}`;
        document.getElementById('bed-studentReg').textContent = data.studentInfo.registration;
        document.getElementById('other-studentName').innerHTML = `<i class="fa-solid fa-user-graduate me-2"></i>${data.studentInfo.name}`;
        document.getElementById('other-studentReg').textContent = data.studentInfo.registration;
        // --- END NEW ---

        // 3. Render the "B.Ed." tab content
        document.getElementById('bed-totalCgpa').textContent = bedCgpa.cgpa.toFixed(4);
        document.getElementById('bed-totalPercentage').textContent = `${bedCgpa.percentage.toFixed(2)}%`;
        document.getElementById('bed-totalMarksObtained').textContent = bedCgpa.totalMarksObtained.toFixed(0);
        document.getElementById('bed-totalMaxMarks').textContent = `/ ${bedCgpa.totalMaxMarks.toFixed(0)}`;
        const bedCircle = document.getElementById('bed-cgpaCircle');
        if (bedCircle) {
            const bedPercentage = (bedCgpa.cgpa / 4.0) * 100;
            setTimeout(() => bedCircle.style.strokeDasharray = `${bedPercentage}, 100`, 100);
        }
        displaySemesterCards('bed-semesterResults', bedData);

        // 4. Render the "Other" tab content
        document.getElementById('other-totalCgpa').textContent = otherCgpa.cgpa.toFixed(4);
        document.getElementById('other-totalPercentage').textContent = `${otherCgpa.percentage.toFixed(2)}%`;
        document.getElementById('other-totalMarksObtained').textContent = otherCgpa.totalMarksObtained.toFixed(0);
        document.getElementById('other-totalMaxMarks').textContent = `/ ${otherCgpa.totalMaxMarks.toFixed(0)}`;
        const otherCircle = document.getElementById('other-cgpaCircle');
        if (otherCircle) {
            const otherPercentage = (otherCgpa.cgpa / 4.0) * 100;
            setTimeout(() => otherCircle.style.strokeDasharray = `${otherPercentage}, 100`, 100);
        }
        displaySemesterCards('other-semesterResults', otherData);

        // 5. --- MODIFIED: Render GPA charts ---
        // Hide the main chart container, which is for non-B.Ed. mode
        gpaChartContainer.style.display = 'none'; 
        // Render the two new charts
        renderBedGpaCharts(bedData.semesters, otherData.semesters);

        // 6. Attach listeners to all new elements
        attachResultEventListeners();

        // 7. Setup attendance button
        setupAttendanceButton();
      }

      // --- NEW Function: Renders either Normal or B.Ed. UI ---
      function renderResults(data) {
        const bedResultContainer = document.getElementById('bedResultContainer');
        
        // Get all the "standard view" elements by their specific IDs/Classes
        const standardGpaCard = document.querySelector('#resultContainer > .gpa-result-card-premium');
        // Get the parent div of the button
        const standardAttendanceBtnDiv = document.getElementById('fetchAttendanceBtn').parentElement; 
        const standardGpaChart = document.getElementById('gpaChartContainer');
        const standardActionButtons = document.querySelector('#resultContainer > .action-buttons-aligned');
        // Get the parent div of the semester grid
        const standardSemesterContainer = document.getElementById('semesterResults').parentElement; 

        if (bedModeActive) {
          // Hide Normal View elements
          if (standardGpaCard) standardGpaCard.style.display = 'none';
          if (standardAttendanceBtnDiv) standardAttendanceBtnDiv.style.display = 'none'; // Hide main button div
          if (standardGpaChart) standardGpaChart.style.display = 'none';
          if (standardActionButtons) standardActionButtons.style.display = 'none';
          if (standardSemesterContainer) standardSemesterContainer.style.display = 'none'; // Hide the container

          // Show B.Ed. Tabbed View
          bedResultContainer.style.display = 'block';
          displayBedResults(data); // This will render the B.Ed. content
        } else {
          // Show Normal View elements
          if (standardGpaCard) standardGpaCard.style.display = 'block';
          if (standardAttendanceBtnDiv) standardAttendanceBtnDiv.style.display = 'block'; // Show main button div
          if (standardGpaChart) standardGpaChart.style.display = 'block';
          if (standardActionButtons) standardActionButtons.style.display = 'flex'; // Use flex for alignment
          if (standardSemesterContainer) standardSemesterContainer.style.display = 'block'; // Show the container

          // Hide B.Ed. Tabbed View
          bedResultContainer.style.display = 'none';
          
          const cgpaData = calculateCGPA(data); // Calculate single, overall CGPA
          displayCGPAResults(data, cgpaData); // Call original display function
        }
      }

      // --- NEW Function: Filters semesters into B.Ed. or Other ---
      function filterSemesters(semesters, includeBed) {
        const filteredSemesters = {};
        
        Object.entries(semesters).forEach(([semesterName, semester]) => {
          // This is the list of courses that *will be displayed* in this tab
          const newCourseList = [];
          
          // --- START FINAL FIX ---
          // Check if the identity flags exist. If not, calculate them.
          // This makes the function work for old profiles loaded from storage.
          let hasBedCourses = semester.hasBedCourses;
          let hasOtherCourses = semester.hasOtherCourses;

          if (hasBedCourses === undefined || hasOtherCourses === undefined) {
            // Flags are missing (old profile), calculate them now.
            hasBedCourses = false;
            hasOtherCourses = false;
            semester.courses.forEach(course => {
              if (BED_COURSES.has(course.code.toUpperCase().trim())) {
                hasBedCourses = true;
              } else {
                hasOtherCourses = true;
              }
            });
            // We'll also check all *other* semesters in processedData
            // in case the course was dragged to another semester
            if (processedData && processedData.semesters) {
                Object.values(processedData.semesters).forEach(s => {
                    s.courses.forEach(c => {
                        // If a course *originally* from this semester is now elsewhere
                        if (c.originalSemester === semester.originalName) {
                            if (BED_COURSES.has(c.code.toUpperCase().trim())) {
                                hasBedCourses = true;
                            } else {
                                hasOtherCourses = true;
                            }
                        }
                    });
                });
            }
          }
          // --- END FINAL FIX ---

          // Now, iterate *again* just to build the *display list*
          semester.courses.forEach(course => {
            const isBedCourse = BED_COURSES.has(course.code.toUpperCase().trim());
            
            if (includeBed && isBedCourse) {
              newCourseList.push(course); // Add to display list for B.Ed. tab
            } else if (!includeBed && !isBedCourse) {
              newCourseList.push(course); // Add to display list for Other tab
            }
          });

          const isForecast = semester.isForecast === true;
          const isBedForecast = semester.isBedForecast === true;

          let shouldBeInThisTab = false;

          if (includeBed) { // We are filtering FOR B.Ed. tab
            // Semester belongs here if it has B.Ed. courses OR is a B.Ed. forecast
            shouldBeInThisTab = hasBedCourses || (isForecast && isBedForecast);
          } else { // We are filtering FOR "Other" tab
            // Semester belongs here if it has Other courses OR is an "Other" forecast
            shouldBeInThisTab = hasOtherCourses || (isForecast && !isBedForecast);
          }
          
          // If the semester belongs in this tab (even if its newCourseList is now empty)
          if (shouldBeInThisTab) {
            filteredSemesters[semesterName] = {
                ...semester,
                courses: newCourseList // This list might be empty, which is what we want
            };
          }
        });
        return filteredSemesters;
      }

      // --- NEW Function: Handles B.Ed. Modal Choice ---
      function handleBedConfirm(isBedStudent, processed) {
        if(bedConfirmationModal) bedConfirmationModal.hide();
        bedModeActive = isBedStudent;
        processed.bedMode = isBedStudent; // Save preference to profile

        // This logic is moved from fetchResult()
        const profiles = getProfiles();
        const studentInfo = processed.studentInfo;
        let baseName = `${studentInfo.name} (${studentInfo.registration})`;
        let finalName = baseName;
        let copyNum = 1;

        const allDisplayNames = Object.values(profiles).map(p => p.displayName);

        while(allDisplayNames.includes(finalName)) {
            finalName = `${baseName} - ${copyNum++}`;
        }

        processed.displayName = finalName;
        processed.createdAt = new Date().toISOString();
        processed.lastModified = new Date().toISOString();
        const newProfileId = `profile_${Date.now()}`;
        profiles[newProfileId] = processed;
        saveProfiles(profiles);
        setActiveProfileId(newProfileId);

        processedData = processed; // *** FIX: Set the global processedData variable ***

        showLoadingStage('complete');
        setTimeout(() => {
          renderResults(processed); // --- MODIFIED: Call new render function
          showLoadingStage(null);
          showToast('New profile created successfully!', 'success');
          updateProfileSwitcher(profiles, newProfileId);
        }, 1000);
      }

      function renderGpaChart() {
          if (!processedData || Object.keys(processedData.semesters).length === 0) {
              gpaChartContainer.style.display = 'none';
              return;
          }

          if (gpaChart) {
              gpaChart.destroy();
          }

          const sortedSemesters = Object.entries(processedData.semesters)
              .sort(([, a], [, b]) => a.sortKey.localeCompare(b.sortKey));

          const labels = sortedSemesters.map(([name]) => name);
          const gpaData = sortedSemesters.map(([, semester]) => formatNumber(semester.gpa, 4));

          const isDarkMode = document.documentElement.getAttribute('data-theme') === 'dark';
          const gridColor = isDarkMode ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.1)';
          const fontColor = isDarkMode ? '#e5e7eb' : '#4b5563';

          gpaChart = new Chart(gpaTrendChartCanvas, {
              type: 'line',
              data: {
                  labels: labels,
                  datasets: [{
                      label: 'Semester GPA',
                      data: gpaData,
                      fill: true,
                      backgroundColor: 'rgba(122, 106, 216, 0.2)',
                      borderColor: 'rgba(122, 106, 216, 1)',
                      tension: 0.3,
                      pointBackgroundColor: 'rgba(122, 106, 216, 1)',
                      pointBorderColor: '#fff',
                      pointHoverRadius: 7,
                      pointHoverBackgroundColor: '#fff',
                      pointHoverBorderColor: 'rgba(122, 106, 216, 1)'
                  }]
              },
              options: {
                  responsive: true,
                  maintainAspectRatio: false,
                  scales: {
                      y: {
                          beginAtZero: true,
                          suggestedMax: 4.0,
                          ticks: { color: fontColor },
                          grid: { color: gridColor }
                      },
                      x: {
                          ticks: { color: fontColor },
                          grid: { color: gridColor }
                      }
                  },
                  plugins: {
                      legend: { display: false },
                      tooltip: {
                          backgroundColor: isDarkMode ? '#1b1f24' : '#fff',
                          titleColor: isDarkMode ? '#fff' : '#1b1f24',
                          bodyColor: isDarkMode ? '#d1d5db' : '#4b5563',
                          borderColor: 'rgba(122, 106, 216, 0.5)',
                          borderWidth: 1,
                          padding: 10,
                          callbacks: {
                              label: context => `GPA: ${context.parsed.y.toFixed(4)}`
                          }
                      }
                  },
                  animation: {
                      duration: 1000,
                      easing: 'easeInOutQuart'
                  }
              }
          });
          gpaChartContainer.style.display = 'block';
      }

          function renderBedGpaCharts(bedSemesters, otherSemesters) {
        const bedChartContainer = document.getElementById('bedGpaChartContainer');
        const otherChartContainer = document.getElementById('otherGpaChartContainer');
        const isDarkMode = document.documentElement.getAttribute('data-theme') === 'dark';
        const gridColor = isDarkMode ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.1)';
        const fontColor = isDarkMode ? '#e5e7eb' : '#4b5563';
        
        // Re-usable options for both charts
        const chartOptions = {
          responsive: true,
          maintainAspectRatio: false,
          scales: {
              y: { beginAtZero: true, suggestedMax: 4.0, ticks: { color: fontColor }, grid: { color: gridColor } },
              x: { ticks: { color: fontColor }, grid: { color: gridColor } }
          },
          plugins: {
              legend: { display: false },
              tooltip: {
                  backgroundColor: isDarkMode ? '#1b1f24' : '#fff',
                  titleColor: isDarkMode ? '#fff' : '#1b1f24',
                  bodyColor: isDarkMode ? '#d1d5db' : '#4b5563',
                  borderColor: 'rgba(122, 106, 216, 0.5)',
                  borderWidth: 1,
                  padding: 10,
                  callbacks: { label: context => `GPA: ${context.parsed.y.toFixed(4)}` }
              }
          },
          animation: { duration: 1000, easing: 'easeInOutQuart' }
        };

        // Render B.Ed. Chart
        if (bedGpaChart) bedGpaChart.destroy(); // Destroy previous chart
        const sortedBedSemesters = Object.entries(bedSemesters).sort(([, a], [, b]) => a.sortKey.localeCompare(b.sortKey));
        if (sortedBedSemesters.length > 0) {
            bedChartContainer.style.display = 'block';
            bedGpaChart = new Chart(document.getElementById('bedGpaTrendChart').getContext('2d'), {
                type: 'line',
                data: {
                    labels: sortedBedSemesters.map(([name]) => name),
                    datasets: [{
                        label: 'B.Ed. GPA',
                        data: sortedBedSemesters.map(([, semester]) => formatNumber(semester.gpa, 4)),
                        fill: true,
                        backgroundColor: 'rgba(122, 106, 216, 0.2)', // Brand color
                        borderColor: 'rgba(122, 106, 216, 1)',
                        tension: 0.3
                    }]
                },
                options: chartOptions
            });
        } else {
            bedChartContainer.style.display = 'none'; // Hide if no data
        }

        // Render Other Chart
        if (otherGpaChart) otherGpaChart.destroy(); // Destroy previous chart
        const sortedOtherSemesters = Object.entries(otherSemesters).sort(([, a], [, b]) => a.sortKey.localeCompare(b.sortKey));
        if (sortedOtherSemesters.length > 0) {
            otherChartContainer.style.display = 'block';
            otherGpaChart = new Chart(document.getElementById('otherGpaTrendChart').getContext('2d'), {
                type: 'line',
                data: {
                    labels: sortedOtherSemesters.map(([name]) => name),
                    datasets: [{
                        label: 'Other GPA',
                        data: sortedOtherSemesters.map(([, semester]) => formatNumber(semester.gpa, 4)),
                        fill: true,
                        backgroundColor: 'rgba(255, 107, 107, 0.2)', // Use Accent color
                        borderColor: 'rgba(255, 107, 107, 1)',
                        tension: 0.3
                    }]
                },
                options: chartOptions
            });
        } else {
            otherChartContainer.style.display = 'none'; // Hide if no data
        }
      }
          

      function attachResultEventListeners() {
        document.querySelectorAll('.clickable-info').forEach(el => el.addEventListener('click', e => showCourseDetails(JSON.parse(e.currentTarget.dataset.course.replace(/&#39;/g, "'")))));
        document.querySelectorAll('.delete-semester').forEach(btn => btn.addEventListener('click', e => deleteSemester(e, e.currentTarget.dataset.semester)));
        document.querySelectorAll('.custom-course-btn').forEach(btn => btn.addEventListener('click', e => openAddCourseModal(e.currentTarget.dataset.semester)));
        
        // --- START: NEW LISTENER FOR PENCIL ICON ---
        document.querySelectorAll('.edit-semester-name').forEach(btn => {
          btn.addEventListener('click', e => openRenameSemesterModal(e.currentTarget.dataset.semester));
        });
        // --- END: NEW LISTENER ---

        if(document.getElementById('copyDetailsIconBtn')) {
            document.getElementById('copyDetailsIconBtn').addEventListener('click', copyDetailsToClipboard);
        }
        document.querySelectorAll('.delete-course').forEach(btn => {
          const course = JSON.parse(btn.dataset.course.replace(/&#39;/g, "'"));
          btn.addEventListener('click', e => modifyCourseState(e, course, btn.dataset.semester, true));
        });
        document.querySelectorAll('.restore-course').forEach(btn => {
          const course = JSON.parse(btn.dataset.course.replace(/&#39;/g, "'"));
          btn.addEventListener('click', e => modifyCourseState(e, course, btn.dataset.semester, false));
        });
        document.querySelectorAll('.semester-card.fade-in-on-scroll:not(.is-visible)').forEach(el => {
            const observer = new IntersectionObserver(entries => {
                if (entries[0].isIntersecting) {
                    entries[0].target.classList.add('is-visible');
                    observer.unobserve(entries[0].target);
                }
            }, { threshold: 0.1 });
            observer.observe(el);
        });
        if (window.innerWidth >= 992) {
          initDragAndDrop();
        }
      }

      function initDragAndDrop() {
          const draggables = document.querySelectorAll('.course-table tr[draggable="true"]');
          const droppables = document.querySelectorAll('.semester-card');

          draggables.forEach(draggable => {
              draggable.addEventListener('dragstart', e => {
                  e.target.classList.add('dragging');
                  const sourceSemester = e.target.closest('.semester-card').dataset.semester;
                  const courseIdentifier = e.target.dataset.courseIdentifier;
                  e.dataTransfer.setData('text/plain', JSON.stringify({ courseIdentifier, sourceSemester }));
              });
              draggable.addEventListener('dragend', e => {
                  e.target.classList.remove('dragging');
              });
          });

          droppables.forEach(droppable => {
              droppable.addEventListener('dragover', e => {
                  e.preventDefault();
                  e.currentTarget.classList.add('drag-over');
              });
              droppable.addEventListener('dragleave', e => {
                  e.currentTarget.classList.remove('drag-over');
              });
              droppable.addEventListener('drop', e => {
                  e.preventDefault();
                  e.currentTarget.classList.remove('drag-over');

                  const data = JSON.parse(e.dataTransfer.getData('text/plain'));
                  const targetSemester = e.currentTarget.dataset.semester;

                  if (data.sourceSemester === targetSemester) {
                      return;
                  }

                  let courseToMove = null;
                  let courseIndex = -1;

                  // Find the course based on its unique identifier
                  const sourceSemesterCourses = processedData.semesters[data.sourceSemester]?.courses;
                  if (sourceSemesterCourses) {
                      courseIndex = sourceSemesterCourses.findIndex((course, index) => {
                          const identifier = `${data.sourceSemester}-${course.code}-${course.total}-${index}`;
                          return identifier === data.courseIdentifier;
                      });
                      if (courseIndex !== -1) {
                          courseToMove = sourceSemesterCourses[courseIndex];
                      }
                  }


                  if (courseToMove && courseIndex > -1) {
                      // --- B.Ed. Drag/Drop Logic ---
                      const isBedCourse = BED_COURSES.has(courseToMove.code.toUpperCase().trim());
                      const targetIsBedTab = e.currentTarget.closest('#bed-tab-content');
                      const targetIsOtherTab = e.currentTarget.closest('#other-tab-content');
                      
                      // Check if the drop is valid in B.Ed. mode
                      if (bedModeActive) {
                          if (isBedCourse && targetIsOtherTab) {
                              showToast(`Cannot move B.Ed. course (${courseToMove.code}) to "Other" tab.`, 'warning');
                              return;
                          }
                          if (!isBedCourse && targetIsBedTab) {
                              showToast(`Cannot move non-B.Ed. course (${courseToMove.code}) to "B.Ed." tab.`, 'warning');
                              return;
                          }
                      }
                      // --- End of B.Ed. Logic ---

                      sourceSemesterCourses.splice(courseIndex, 1); // Remove from source
                      processedData.semesters[targetSemester].courses.push(courseToMove); // Add to target
                      recalculateAndDisplay(); // Update UI
                      showToast(`Moved ${courseToMove.code} to ${targetSemester}`, 'success');
                      addStatusMessage(`Moved course ${courseToMove.code} from ${data.sourceSemester} to ${targetSemester}`, 'info');
                  } else {
                      showToast('Could not move course. Data might be out of sync.', 'error');
                      console.error('Course mismatch or not found. Identifier:', data.courseIdentifier, 'Index:', courseIndex);
                  }
              });
          });
      }

      // ---
      // --- REVISED showCourseDetails Function (UI/UX Improv. & Fixes) ---
      // ---
      function showCourseDetails(course) {
        // --- Fix 1: Semester Name Formatting ---
        let formattedSemester = course.originalSemester || 'Unknown Semester';
        // Remove " Semester" and format year range (e.g., "Winter Semester 2020-2021" -> "Winter 2020-21")
        formattedSemester = formattedSemester.replace(' Semester', ''); // Remove " Semester"
        formattedSemester = formattedSemester.replace(/(\d{4})-(\d{4})/, (match, y1, y2) => `${y1}-${y2.substring(2)}`); // Format year range

        // Set Modal Title
        document.getElementById('courseDetailsModalTitle').textContent = `${course.code} - ${course.title || 'N/A'}`;

        // --- Fix 2 & UI Improvement: Modal Body Structure ---
        const modalBody = document.getElementById('courseDetailsModalBody');
        modalBody.innerHTML = `
          <div class="mb-3 border-bottom pb-3">
            <h6 class="text-muted fw-bold small text-uppercase mb-2">Details</h6>
            <div class="row g-2">
              <div class="col-12 col-sm-6">
                <p class="mb-1 small"><i class="fa-solid fa-chalkboard-user fa-fw me-2 text-primary"></i><strong>Teacher:</strong> ${course.teacher || 'N/A'}</p>
              </div>
              <div class="col-12 col-sm-6">
                <p class="mb-1 small"><i class="fa-solid fa-calendar-alt fa-fw me-2 text-primary"></i><strong>Semester:</strong> ${formattedSemester}</p>
              </div>
              <div class="col-12">
                 <p class="mb-0 small"><i class="fa-solid fa-hourglass-half fa-fw me-2 text-primary"></i><strong>Credit Hours:</strong> ${course.creditHoursDisplay || course.creditHours}</p>
              </div>
            </div>
          </div>

          <div class="mb-3 border-bottom pb-3">
            <h6 class="text-muted fw-bold small text-uppercase mb-2">Marks Breakdown</h6>
            <div class="row g-2">
              <div class="col-6 col-sm-3">
                <p class="mb-1 small text-center text-sm-start"><i class="fa-solid fa-file-pen fa-fw me-1 text-info"></i><strong>Mid:</strong> ${course.mid || 'N/A'}</p>
              </div>
              <div class="col-6 col-sm-3">
                <p class="mb-1 small text-center text-sm-start"><i class="fa-solid fa-clipboard fa-fw me-1 text-info"></i><strong>Assign:</strong> ${course.assignment || 'N/A'}</p>
              </div>
              <div class="col-6 col-sm-3">
                 <p class="mb-1 small text-center text-sm-start"><i class="fa-solid fa-flag-checkered fa-fw me-1 text-info"></i><strong>Final:</strong> ${course.final || 'N/A'}</p>
              </div>
               ${course.practical && course.practical !== '0' ? `
                 <div class="col-6 col-sm-3">
                   <p class="mb-1 small text-center text-sm-start"><i class="fa-solid fa-flask-vial fa-fw me-1 text-info"></i><strong>Prac:</strong> ${course.practical}</p>
                 </div>
               ` : ''}
            </div>
          </div>

          <div>
             <h6 class="text-muted fw-bold small text-uppercase mb-2">Result</h6>
             <div class="d-flex flex-wrap justify-content-around align-items-center bg-light rounded p-2" style="background-color: rgba(122, 106, 216, 0.05) !important;">
                 <div class="text-center px-2">
                     <span class="small text-muted">Total Marks</span>
                     <p class="fs-5 fw-bold mb-0 text-primary">${course.marks !== undefined ? course.marks : 'N/A'}</p>
                 </div>
                 <div class="text-center px-2">
                     <span class="small text-muted">Grade</span>
                     <p class="fs-5 mb-0"><span class="grade-badge grade-${course.grade}">${course.grade || 'N/A'}</span></p>
                 </div>
                 <div class="text-center px-2">
                     <span class="small text-muted">Quality Points</span>
                     <p class="fs-5 fw-bold mb-0 text-primary">${course.qualityPoints !== undefined ? course.qualityPoints.toFixed(2) : 'N/A'}</p>
                 </div>
             </div>
          </div>

          ${course.isExtraEnrolled ? `<div class="alert alert-warning d-flex align-items-center mt-3 small p-2"><i class="fa-solid fa-info-circle me-2"></i> This is a repeated course attempt, and its marks are not the highest achieved. It does not count towards the CGPA calculation shown.</div>` : ''}
          ${course.isRepeated && !course.isExtraEnrolled ? `<div class="alert alert-success d-flex align-items-center mt-3 small p-2"><i class="fa-solid fa-check-circle me-2"></i> This is the highest scoring attempt for this repeated course and is used in CGPA calculation.</div>` : ''}
          ${course.isCustom ? `<div class="alert alert-info d-flex align-items-center mt-3 small p-2"><i class="fa-solid fa-pencil me-2"></i> This is a custom course added manually${course.source === 'attendance' ? ' (imported from Attendance System)' : ''}.</div>` : ''}`;

        courseDetailsModal.show();
      }

      function openAddCourseModal(semesterName) {
        document.getElementById('addCourseSemester').value = semesterName;
        addCourseForm.reset();
        addCourseModal.show();
      }

      function addCustomCourse() {
        const semesterName = document.getElementById('addCourseSemester').value;
        const courseCode = document.getElementById('courseCode').value.trim().toUpperCase();
        const courseTitle = document.getElementById('courseTitle').value.trim();
        const creditHours = parseInt(document.getElementById('creditHours').value);
        const marks = parseFloat(document.getElementById('courseMarks').value);
        if (!courseCode || !courseTitle || !creditHours || isNaN(marks)) {
          showToast('Please fill all fields correctly', 'error');
          return;
        }
        if (marks < 0 || marks > 100) {
             showToast('Marks must be between 0 and 100', 'error');
             return;
        }
        
        // --- B.Ed. Validation ---
        if (bedModeActive) {
            const isBedCourse = BED_COURSES.has(courseCode);
            const currentTab = document.querySelector('#bedTab .nav-link.active').id;
            
            if (isBedCourse && currentTab === 'other-tab') {
                showToast(`Cannot add B.Ed. course (${courseCode}) to "Other" tab.`, 'warning');
                return;
            }
            if (!isBedCourse && currentTab === 'bed-tab') {
                showToast(`Cannot add non-B.Ed. course (${courseCode}) to "B.Ed." tab.`, 'warning');
                return;
            }
        }
        // --- End of B.Ed. Validation ---

        const grade = calculateCustomGrade(marks, creditHours);
        const qualityPoints = calculateQualityPoints(marks, creditHours, grade);

        const newCourse = {
            code: courseCode, title: courseTitle, creditHours, creditHoursDisplay: `${creditHours}(${creditHours}-0)`, marks,
            qualityPoints: qualityPoints, grade: grade,
            semesterName, teacher: 'Custom', mid: 'N/A', assignment: 'N/A', final: marks, practical: 'N/A', total: marks,
            isExtraEnrolled: false, isRepeated: false, isDeleted: false, isCustom: true, originalSemester: semesterName // Add originalSemester for consistency
        };

         // Check if course already exists (non-deleted) in the same semester
        const semester = processedData.semesters[semesterName];
        if (semester && semester.courses.some(c => !c.isDeleted && c.code.toUpperCase() === newCourse.code)) {
            showToast(`Course ${newCourse.code} already exists in ${semesterName}. Edit or delete the existing one first.`, 'warning');
            return;
        }

        processedData.semesters[semesterName].courses.push(newCourse);
        recalculateAndDisplay();
        addCourseModal.hide();
        showToast(`Course ${courseCode} added`, 'success');
        addStatusMessage(`Added custom course: ${courseCode} to ${semesterName}`, 'info');
      }

      function deleteSemester(event, semesterName) {
        event.preventDefault();
        if (!processedData || !processedData.semesters[semesterName]) return;

        deletedSemesters[semesterName] = JSON.parse(JSON.stringify(processedData.semesters[semesterName]));
        delete processedData.semesters[semesterName];

        recalculateAndDisplay();

        showUndoNotification(`Semester "${semesterName}" deleted`, () => undoDeleteSemester(semesterName));
        addStatusMessage(`Deleted semester: ${semesterName}`, 'info');
      }

      function showUndoNotification(message, undoCallback) {
        document.getElementById('undo-notification')?.remove();
        const notification = document.createElement('div');
        notification.id = 'undo-notification';
        notification.className = 'undo-notification';
        notification.innerHTML = `<span>${message}</span> <button class="undo-btn">Undo</button>`;
        document.body.appendChild(notification);
        notification.querySelector('.undo-btn').onclick = () => {
            undoCallback();
            notification.remove();
        };
        setTimeout(() => notification.remove(), 5000);
      }

      function undoDeleteSemester(semesterName) {
        if (!deletedSemesters[semesterName]) return;

        processedData.semesters[semesterName] = deletedSemesters[semesterName];
        delete deletedSemesters[semesterName];

        recalculateAndDisplay();
        addStatusMessage(`Restored semester: ${semesterName}`, 'info');
      }

      function modifyCourseState(event, course, semesterName, isDeleted) {
        event.preventDefault();
        const semester = processedData.semesters[semesterName];
        if (!semester) return;

        // Find course using a more robust comparison, including custom status
        const courseIndex = semester.courses.findIndex(c =>
            c.code === course.code &&
            c.title === course.title &&
            c.creditHours === course.creditHours &&
            c.marks === course.marks &&
            c.isCustom === course.isCustom // Crucial for distinguishing identical custom courses
        );


        if (courseIndex !== -1) {
          semester.courses[courseIndex].isDeleted = isDeleted;
          recalculateAndDisplay();
          const action = isDeleted ? 'Deleted' : 'Restored';
          showToast(`Course ${course.code} ${action.toLowerCase()}`, 'info');
          addStatusMessage(`${action} course: ${course.code} from ${semesterName}`, 'info');
        } else {
          console.error("Could not find course to modify state:", course, "in semester:", semesterName);
          showToast(`Error modifying course ${course.code}`, 'error');
        }
      }


      function recalculateAndDisplay() {
        saveActiveProfile();
        // Re-render the entire UI based on the current mode and modified data
        renderResults(processedData);
      }

      function addForecastSemester() {
        // --- NEW: Check which tab is active ---
        let isForBedTab = false;
        if (bedModeActive) {
            const activeTabId = document.querySelector('#bedTab .nav-link.active').id;
            if (activeTabId === 'bed-tab') {
                isForBedTab = true;
            }
        }
        // --- END NEW ---

        let forecastCount = 1;
        while (`Forecast ${forecastCount}` in processedData.semesters) {
            forecastCount++;
        }
        const newSemesterName = `Forecast ${forecastCount}`;
        processedData.semesters[newSemesterName] = {
            originalName: newSemesterName,
            sortKey: getSemesterOrderKey(newSemesterName),
            courses: [],
            isForecast: true,
            isBedForecast: isForBedTab // <-- ADD THIS NEW FLAG
        };
        
        recalculateAndDisplay(); // This renders the new card
        showToast(`Added "${newSemesterName}"`, 'success');
        addStatusMessage(`Added forecast semester: ${newSemesterName}`, 'info');

        // --- START: NEW SCROLL-TO-ELEMENT LOGIC ---
        setTimeout(() => {
          const newCard = document.querySelector(`[data-semester="${newSemesterName}"]`);
          if (newCard) {
            newCard.scrollIntoView({ behavior: 'smooth', block: 'center' });
            // Optional: Add a subtle flash animation
            newCard.style.transition = 'background-color 0.5s ease-out';
            newCard.style.backgroundColor = 'rgba(122, 106, 216, 0.1)';
            setTimeout(() => {
                newCard.style.backgroundColor = '';
            }, 1000);
          }
        }, 100); // Small delay to ensure DOM is updated
        // --- END: NEW SCROLL-TO-ELEMENT LOGIC ---
      }

      // NEW CODE (replace with this)
      function openRenameSemesterModal(oldSemesterName) {
        if (!processedData.semesters[oldSemesterName]) return;
        document.getElementById('newSemesterName').value = oldSemesterName;
        saveSemesterNameBtn.dataset.oldName = oldSemesterName; // Store old name
        renameSemesterModal.show();
      }

      // ADD THIS NEW FUNCTION (e.g., after openRenameSemesterModal)
      function renameSemester() {
        const oldSemesterName = saveSemesterNameBtn.dataset.oldName;
        const newSemesterName = document.getElementById('newSemesterName').value.trim();

        if (!newSemesterName || newSemesterName === "") {
          showToast("Semester name cannot be empty.", 'warning');
          return;
        }

        if (newSemesterName === oldSemesterName) {
          renameSemesterModal.hide();
          return;
        }

        if (processedData.semesters[newSemesterName]) {
          showToast(`Semester name "${newSemesterName}" already exists.`, 'error');
          return;
        }

        // Rename: Copy data, delete old, update properties
        processedData.semesters[newSemesterName] = processedData.semesters[oldSemesterName];
        delete processedData.semesters[oldSemesterName];
        
        processedData.semesters[newSemesterName].originalName = newSemesterName;
        processedData.semesters[newSemesterName].sortKey = getSemesterOrderKey(newSemesterName);
        // The isForecast flag is automatically carried over
        
        recalculateAndDisplay();
        renameSemesterModal.hide();
        showToast(`Semester renamed to "${newSemesterName}"`, 'success');
        addStatusMessage(`Renamed semester "${oldSemesterName}" to "${newSemesterName}"`, 'info');
      }
      
      function copyDetailsToClipboard() {
          if (!processedData) return;
          const textToCopy = `Name: ${processedData.studentInfo.name}\nRegistration: ${processedData.studentInfo.registration}\nCGPA: ${totalCgpa.textContent}\nPercentage: ${totalPercentage.textContent}`;
          navigator.clipboard.writeText(textToCopy).then(() => {
              showToast('Details copied to clipboard!', 'success');
          }, (err) => {
              showToast('Failed to copy details.', 'error');
              console.error('Clipboard copy failed: ', err);
          });
      }

      function generatePDF() {
        if (!processedData) {
            showToast('No data to download', 'error');
            return;
        }

        // --- B.Ed. PDF Logic ---
        // Determine which dataset to use for the PDF
        let dataToPrint, titleSuffix;
        if (bedModeActive) {
            const activeTabId = document.querySelector('#bedTab .nav-link.active').id;
            if (activeTabId === 'bed-tab') {
                const bedSemesters = filterSemesters(processedData.semesters, true);
                dataToPrint = { ...processedData, semesters: bedSemesters };
                titleSuffix = 'B.Ed. Program';
            } else { // 'other-tab'
                const otherSemesters = filterSemesters(processedData.semesters, false);
                dataToPrint = { ...processedData, semesters: otherSemesters };
                titleSuffix = 'Other Programs';
            }
        } else {
            // Normal mode, print all
            dataToPrint = processedData;
            titleSuffix = 'Overall';
        }
        // --- End of B.Ed. PDF Logic ---


        addStatusMessage(`Generating premium PDF report (${titleSuffix})...`, 'info');
        showLoadingStage('processing');

        try {
            const { jsPDF } = window.jspdf;
            const pdf = new jsPDF({ orientation: 'p', unit: 'mm', format: 'a4' });
            
            // --- Use the *calculated* CGPA for the selected dataset ---
            const cgpaData = calculateCGPA(dataToPrint);

            const pageMargin = 15;
            const pageWidth = pdf.internal.pageSize.getWidth();
            const pageHeight = pdf.internal.pageSize.getHeight();
            const availableWidth = pageWidth - (2 * pageMargin);
            const colors = {
                primary: '#7a6ad8',
                textDark: '#1b1f24',
                textLight: '#4b5563',
                line: '#e0e0e0',
                fillLight: '#f8f9ff',
            };
            let lastY = 0;

            const drawFirstPageHeader = () => {
                pdf.setFontSize(18);
                pdf.setTextColor(colors.primary);
                pdf.setFont('helvetica', 'bold');
                pdf.text("University of Agriculture Faisalabad (UAF)", pageWidth / 2, 20, { align: 'center' });

                pdf.setFontSize(12);
                pdf.setTextColor(colors.textLight);
                pdf.setFont('helvetica', 'normal');
                
                // --- PDF TITLE CHANGE ---
                let transcriptTitle = "Unofficial Academic Transcript";
                if (titleSuffix === 'B.Ed. Program') {
                    transcriptTitle += ` (${titleSuffix})`; // Only add suffix for B.Ed.
                }
                pdf.text(transcriptTitle, pageWidth / 2, 28, { align: 'center' });
                // --- END PDF TITLE CHANGE ---

                pdf.setDrawColor(colors.primary);
                pdf.setLineWidth(0.5);
                pdf.line(pageMargin, 35, pageWidth - pageMargin, 35);
                lastY = 35;
            };

            drawFirstPageHeader();

            const topBoxY = lastY + 10;
            const boxHeight = 45;
            const gap = 5;
            const leftBoxWidth = availableWidth * 0.4;
            const rightBoxWidth = availableWidth - leftBoxWidth - gap;
            const rightBoxX = pageMargin + leftBoxWidth + gap;

            pdf.setFillColor(colors.fillLight);
            pdf.roundedRect(pageMargin, topBoxY, leftBoxWidth, boxHeight, 3, 3, 'F');
            pdf.setFontSize(11);
            pdf.setFont('helvetica', 'bold');
            pdf.setTextColor(colors.textDark);
            pdf.text("Student Information", pageMargin + 5, topBoxY + 8);
            pdf.setDrawColor(colors.line);
            pdf.line(pageMargin + 5, topBoxY + 11, pageMargin + leftBoxWidth - 5, topBoxY + 11);

            pdf.setFontSize(12);
            pdf.setFont('helvetica', 'bold');
            pdf.setTextColor(colors.primary);
            pdf.text(dataToPrint.studentInfo.name, pageMargin + 5, topBoxY + 25, { maxWidth: leftBoxWidth - 10 });

            pdf.setFontSize(8);
            pdf.setFont('helvetica', 'normal');
            pdf.setTextColor(colors.textLight);
            pdf.text(dataToPrint.studentInfo.registration, pageMargin + 5, topBoxY + 30);

            pdf.setFillColor(colors.fillLight);
            pdf.roundedRect(rightBoxX, topBoxY, rightBoxWidth, boxHeight, 3, 3, 'F');
            pdf.setFontSize(11);
            pdf.setFont('helvetica', 'bold');
            pdf.setTextColor(colors.textDark);
            
            // --- PDF ACADEMIC SUMMARY CHANGE ---
            pdf.text(`Academic Summary`, rightBoxX + 5, topBoxY + 8); 
            // --- END PDF ACADEMIC SUMMARY CHANGE ---
            
            pdf.line(rightBoxX + 5, topBoxY + 11, rightBoxX + rightBoxWidth - 5, topBoxY + 11);

            pdf.setFontSize(22);
            pdf.setFont('helvetica', 'bold');
            pdf.setTextColor(colors.primary);
            pdf.text(formatNumber(cgpaData.cgpa, 4).toFixed(4), rightBoxX + 5, topBoxY + 25);
            pdf.setFontSize(8);
            pdf.setTextColor(colors.textLight);
            
            // --- PDF CGPA LABEL CHANGE ---
            pdf.text(`Overall CGPA`, rightBoxX + 5, topBoxY + 29); 
            // --- END PDF CGPA LABEL CHANGE ---

            const statsStartX = rightBoxX + 40;
            pdf.setFont('helvetica', 'bold');
            pdf.text("Percentage:", statsStartX, topBoxY + 20);
            pdf.text("Total Credits:", statsStartX, topBoxY + 28);
            pdf.text("Total Marks:", statsStartX, topBoxY + 36);

            pdf.setFont('helvetica', 'normal');
            pdf.setTextColor(colors.textDark);
            pdf.text(`${formatNumber(cgpaData.percentage, 2).toFixed(2)}%`, statsStartX + 25, topBoxY + 20);
            pdf.text(cgpaData.totalCreditHours.toString(), statsStartX + 25, topBoxY + 28);
            pdf.text(`${cgpaData.totalMarksObtained.toFixed(0)} / ${cgpaData.totalMaxMarks}`, statsStartX + 25, topBoxY + 36);

            lastY = topBoxY + boxHeight;

            let semesterIndex = 0;
            Object.keys(dataToPrint.semesters) // --- Use dataToPrint ---
                .sort((a, b) => dataToPrint.semesters[a].sortKey.localeCompare(dataToPrint.semesters[b].sortKey))
                .forEach(semesterName => {
                    semesterIndex++;
                    const semester = dataToPrint.semesters[semesterName]; // --- Use dataToPrint ---
                    const activeCourses = semester.courses.filter(c => !c.isDeleted);
                    if (activeCourses.length === 0) return;

                    const semesterSummary = `GPA: ${formatNumber(semester.gpa, 4).toFixed(4)}  |  Credit Hours: ${semester.totalCreditHours}  |  Marks: ${semester.totalMarksObtained.toFixed(0)}/${semester.totalMaxMarks}`;

                    if (lastY + 30 > pageHeight - 30) { // Added margin check for footer
                        pdf.addPage();
                        lastY = 20; // Reset Y for new page
                    }
                    const semesterHeaderY = lastY + 12;

                    pdf.setFontSize(14);
                    pdf.setFont('helvetica', 'bold');
                    pdf.setTextColor(colors.primary);
                    pdf.text(`${semesterIndex}. ${semesterName}`, pageMargin, semesterHeaderY);

                    pdf.setFontSize(9);
                    pdf.setFont('helvetica', 'bold');
                    pdf.setTextColor(colors.textDark);
                    pdf.text(semesterSummary, pageWidth - pageMargin, semesterHeaderY, { align: 'right' });

                    lastY = semesterHeaderY + 2;

                    const head = [['Course Code', 'Course Title', 'CH', 'Marks', 'Grade']];
                    const body = activeCourses.map(c => [
                        c.code + (c.isCustom ? '*' : ''), // Mark custom courses
                        c.title || (c.isCustom ? 'Custom Course' : 'N/A'),
                        c.creditHoursDisplay || c.creditHours,
                        c.marks.toFixed(0),
                        c.grade
                    ]);


                    pdf.autoTable({
                        head: head,
                        body: body,
                        startY: lastY,
                        margin: { left: pageMargin, right: pageMargin },
                        headStyles: { fillColor: colors.primary, textColor: '#ffffff', fontStyle: 'bold', halign: 'center', valign: 'middle' },
                        columnStyles: {
                            0: { halign: 'left', cellWidth: availableWidth * 0.18 },
                            1: { halign: 'left', cellWidth: availableWidth * 0.46, cellPadding: { left: 2 } },
                            2: { halign: 'center', cellWidth: availableWidth * 0.12 },
                            3: { halign: 'center', cellWidth: availableWidth * 0.12 },
                            4: { halign: 'center', cellWidth: availableWidth * 0.12 }
                        },
                        styles: { valign: 'middle', cellPadding: 2.2, fontSize: 9, overflow: 'linebreak' },
                        alternateRowStyles: { fillColor: '#f8f9ff' },
                         didDrawPage: (data) => {
                             // Reset lastY for autoTable pagination
                             lastY = data.cursor.y;
                         }
                    });
                    // Update lastY after table drawing
                     lastY = pdf.lastAutoTable.finalY;


                    if (lastY < pageHeight - 30) { // Check against footer margin
                         pdf.setDrawColor(colors.line);
                         pdf.setLineWidth(0.3);
                         pdf.line(pageMargin, lastY + 6, pageWidth - pageMargin, lastY + 6);
                         lastY += 6;
                    }
                });

            // Footer for all pages
            const totalPages = pdf.internal.getNumberOfPages();
            for (let i = 1; i <= totalPages; i++) {
                pdf.setPage(i);
                pdf.setFontSize(9);
                pdf.setTextColor(colors.textLight);
                pdf.setFont('helvetica', 'italic');
                const footerY = pageHeight - 15;

                pdf.text("Generated by UAF CGPA Calculator - M Saqlain (https://uafcgpacalculator.vercel.app)", pageWidth / 2, footerY, { align: 'center' });
                pdf.text("This is an unofficial transcript. * indicates a custom course added manually.", pageWidth / 2, footerY + 5, { align: 'center' });

                pdf.setFontSize(8).setTextColor('#b0b0b0');
                pdf.text(`Page ${i} of ${totalPages}`, pageWidth - pageMargin, pageHeight - 10, { align: 'right' });
            }

            // --- Use titleSuffix for filename ---
            const safeSuffix = titleSuffix.replace(/ /g, '_');
            pdf.save(`UAF_Transcript_${dataToPrint.studentInfo.registration}_${safeSuffix}.pdf`);
            addStatusMessage('PDF report generated successfully', 'success');
            showToast('PDF downloaded!', 'success');
        } catch (e) {
            addStatusMessage(`Error generating PDF: ${e.message}`, 'error');
            showToast('Error generating PDF', 'error');
            console.error("PDF generation error: ", e);
        } finally {
            showLoadingStage(null);
        }
      }

       // *** 1. ADD THIS NEW HELPER FUNCTION ***
    // This function contains the new deduplication logic (Req 2)
    // and is called by fetchAttendanceData either with fresh or cached data.
    function processAttendanceData(data) {
        if (!data || !data.resultData) {
            showToast('No attendance data to process.', 'info');
            return;
        }

        addStatusMessage(`Processing ${data.resultData.length} records from Attendance System...`, 'info');

        // --- REQ 2: New Deduplication Logic ---
        // 1. Create a global map of all existing LMS courses
        // Key: "CHEM-401", Value: Set {"75|B", "80|A"}
        const globalLmsCourseMap = new Map();
        Object.values(processedData.semesters).forEach(sem => {
            sem.courses.forEach(course => {
                // Only check against courses not deleted and not *already* from attendance
                if (!course.isDeleted && course.source !== 'attendance') {
                    const code = course.code.toUpperCase().trim();
                    // Use parseFloat for marks and handle potential 'N/A' grades
                    const marks = parseFloat(course.marks);
                    const grade = (course.grade || 'N/A').toUpperCase().trim();
                    const key = `${marks}|${grade}`;
                    
                    if (!globalLmsCourseMap.has(code)) {
                        globalLmsCourseMap.set(code, new Set());
                    }
                    globalLmsCourseMap.get(code).add(key);
                }
            });
        });
        // --- End of Map Build ---

        // 2. Process ALL attendance courses, flagging duplicates based on the new global map
        const allAttendanceCourses = [];
        data.resultData.forEach(attCourse => {
            const courseCode = (attCourse.CourseCode || '').toUpperCase().trim();
            const semesterName = processSemesterName(attCourse.Semester);
            const marks = parseFloat(attCourse.Totalmark || '0');
            const grade = (attCourse.Grade || 'N/A').toUpperCase().trim();
            const globalKey = `${marks}|${grade}`;

            let isDuplicate = false;

            // REQ 2: Check if this exact code, mark, and grade combo exists *anywhere* in the LMS data
            if (globalLmsCourseMap.has(courseCode) && globalLmsCourseMap.get(courseCode).has(globalKey)) {
                isDuplicate = true;
            }

            // Also check if it's *already* imported from attendance (original logic, still good)
            const semesterExists = processedData.semesters[semesterName];
            if (!isDuplicate && semesterExists && semesterExists.courses.some(c => 
                    c.code.toUpperCase().trim() === courseCode && 
                    c.isCustom && 
                    c.source === 'attendance'
                )) {
                isDuplicate = true; // Already imported, treat as duplicate
            }

            allAttendanceCourses.push({
                code: (attCourse.CourseCode || '').trim(), // Keep original case for display
                title: attCourse.CourseName || 'N/A',
                semester: semesterName,
                marks: marks,
                grade: (attCourse.Grade || 'N/A'), // Keep original case for display
                teacher: attCourse.TeacherName || 'N/A',
                mid: attCourse.Mid || '0',
                assignment: attCourse.Assigment || '0', // Corrected typo from API
                final: attCourse.Final || '0',
                practical: attCourse.Practical || '0',
                isDuplicate: isDuplicate 
            });
        });

        if (allAttendanceCourses.length > 0) {
            const importableCount = allAttendanceCourses.filter(c => !c.isDuplicate).length;
            addStatusMessage(`${allAttendanceCourses.length} courses found, ${importableCount} are new/importable. Showing import dialog.`, 'info');
            renderAttendanceImportModal(allAttendanceCourses);
            attendanceImportModal.show();
        } else {
            showToast('No courses found in Attendance System.', 'info');
            addStatusMessage('Attendance System search returned no courses.', 'success');
        }
    }


    // *** 2. REPLACE YOUR OLD FUNCTION WITH THIS UPDATED ONE ***
    async function fetchAttendanceData(clickedButton) { // <-- ACCEPTS THE BUTTON
        if (!processedData || !processedData.studentInfo || !processedData.studentInfo.registration) {
            showToast('Please fetch results first.', 'warning');
            return;
        }
        const regNum = processedData.studentInfo.registration;
        const cacheKey = `uafAttendanceCache_${regNum}`;
        const TEN_MINUTES_MS = 10 * 60 * 1000; // 10 minutes

        // --- Caching Logic ---
        try {
            const cachedDataJSON = localStorage.getItem(cacheKey);
            if (cachedDataJSON) {
                const cachedData = JSON.parse(cachedDataJSON);
                const cacheAge = Date.now() - cachedData.timestamp;

                if (cacheAge < TEN_MINUTES_MS) {
                    addStatusMessage(`Using cached attendance data (fetched ${Math.round(cacheAge / 1000 / 60)} mins ago).`, 'info');
                    showToast('Using cached attendance data.', 'info');
                    processAttendanceData(cachedData.data); // Process cached data
                    return; // Stop execution, don't fetch
                } else {
                    addStatusMessage('Cached attendance data is stale (> 10 mins). Fetching new data.', 'info');
                    localStorage.removeItem(cacheKey); // Clear stale data
                }
            }
        } catch (e) {
            console.error('Error reading cache:', e);
            localStorage.removeItem(cacheKey); // Clear corrupted cache
        }
        // --- End of Caching Logic ---

        addStatusMessage(`Fetching results from Attendance System for: ${regNum}`, 'info');
        
        // --- NEW: Show loading animation on the clicked button ---
        if (clickedButton) {
            clickedButton.disabled = true;
            clickedButton.innerHTML = '<i class="fa-solid fa-spinner fa-spin me-2"></i>Fetching...';
        }

        try {
            const response = await fetch(`${ATTENDANCE_API_ENDPOINT}&registrationNumber=${encodeURIComponent(regNum)}`);
            const data = await response.json();

            if (!response.ok || !data.success) {
                throw new Error(data.message || `Server responded with status ${response.status}`);
            }
            
            addStatusMessage(`Successfully fetched ${data.resultData.length} records from Attendance System`, 'success');

            // --- Store in cache on successful fetch ---
            try {
                localStorage.setItem(cacheKey, JSON.stringify({ timestamp: Date.now(), data: data }));
                addStatusMessage('Saved attendance data to cache.', 'info');
            } catch (e) {
                console.error('Error saving to cache:', e);
                addStatusMessage('Could not save attendance data to cache (storage might be full).', 'warning');
            }

            // Call the new helper function to process and render
            processAttendanceData(data);

        } catch (error) {
            console.error("Attendance Fetch Error:", error);
            let userMessage = 'Could not retrieve Attendance System results. The server may be offline or the registration number is incorrect.';
            if (error.message.includes('timed out')) {
                userMessage = 'Connection to Attendance System timed out. Please try again later.';
            } else if (error.message.includes('No results found')) {
                userMessage = error.message; 
            }
            addStatusMessage(`Error fetching from Attendance System: ${error.message}`, 'error');
            showToast(userMessage, 'error');
        } finally {
            // --- NEW: Don't reset the button here ---
            // The setup function will be called by other functions
            // that modify the state (revert, import)
            
            // If no data was found or an error occurred, we must reset the buttons
            if (importedAttendanceCourses.length === 0) {
                 setupAttendanceButton();
            }
        }
    }


      function renderAttendanceImportModal(courses) {
        const listEl = document.getElementById('attendanceCourseList');
        const listElContainer = listEl.parentNode; // Get parent to replace
        let newListEl = listEl.cloneNode(false); // Create empty new list
        
        const toggleSwitch = document.getElementById('toggleAllCourses');
        const selectAllCheckbox = document.getElementById('toggleSelectAllCourses');
        const courseCountEl = document.getElementById('attendanceCourseCount');
        const modalTitle = document.getElementById('attendanceModalTitle');
        const modalDescription = document.getElementById('attendanceModalDescription');
        
        if (courses.length === 0) {
            newListEl.innerHTML = '<p class="text-center text-muted p-3">No courses found in Attendance System.</p>';
            importAttendanceCoursesBtn.disabled = true;
            if (toggleSwitch) toggleSwitch.closest('.d-flex').style.display = 'none';
            courseCountEl.textContent = 'Total: 0';
            listElContainer.replaceChild(newListEl, listEl); // Replace old list
            updateAttendanceCounts(); // Disable 'Select All'
            return;
        }

        let missingCoursesFound = false;
        
        courses.forEach((course, index) => {
            const courseId = `att-course-${index}`;
            const selectId = `att-ch-${index}`;
            const item = document.createElement('div');
            item.className = 'attendance-course-item';
            
            if (course.isDuplicate) {
                item.classList.add('duplicate-course');
                item.style.display = 'none';
            } else {
                missingCoursesFound = true;
            }

            let labelText = '';
            if (course.title && course.title.toLowerCase() !== 'n/a' && course.title.trim() !== '') {
                labelText = `${course.title} - `;
            }
            labelText += `Marks: ${course.marks}, Grade: ${course.grade}`;

            item.innerHTML = `
                <div class="form-check">
                    <input class="form-check-input" type="checkbox" value="${index}" id="${courseId}" 
                        ${course.isDuplicate ? 'disabled' : 'checked'}>
                    <label class="form-check-label" for="${courseId}">
                        <strong>${course.code}</strong> (${course.semester})
                        ${course.isDuplicate ? '<span class="badge bg-success-subtle text-success-emphasis rounded-pill ms-1">In LMS</span>' : ''}
                        <small class="d-block text-muted">${labelText}</small>
                    </label>
                </div>
                <div class="import-ch-select">
                    <label for="${selectId}" class="form-label mb-0 small me-2">CH:</label>
                    <select class="form-select form-select-sm" id="${selectId}" ${course.isDuplicate ? 'disabled' : ''} style="width: 75px;">
                        ${[1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map(ch => `<option value="${ch}" ${ch === 3 ? 'selected' : ''}>${ch}</option>`).join('')}
                    </select>
                </div>
            `;
            item.querySelector(`#${courseId}`).dataset.courseData = JSON.stringify(course);
            newListEl.appendChild(item);
        });

        // Replace the old list with the new one to attach fresh listeners
        listElContainer.replaceChild(newListEl, listEl);

        // Attach listener for individual checkboxes
        newListEl.addEventListener('change', (e) => {
            if (e.target.classList.contains('form-check-input')) {
                updateAttendanceCounts();
            }
        });

        // --- Handle Toggles ---
        if (toggleSwitch) {
            toggleSwitch.closest('.d-flex').style.display = 'flex';
            toggleSwitch.checked = false; 
            
            const newToggle = toggleSwitch.cloneNode(true);
            toggleSwitch.parentNode.replaceChild(newToggle, toggleSwitch);
            
            newToggle.addEventListener('change', (e) => {
                const showAll = e.target.checked;
                newListEl.querySelectorAll('.duplicate-course').forEach(item => {
                    item.style.display = showAll ? 'flex' : 'none'; 
                });
                updateAttendanceCounts(); // Update counts and 'Select All' state
            });
        }
        
        if (selectAllCheckbox) {
            selectAllCheckbox.checked = false;
            
            const newSelectAll = selectAllCheckbox.cloneNode(true);
            selectAllCheckbox.parentNode.replaceChild(newSelectAll, selectAllCheckbox);

            newSelectAll.addEventListener('change', (e) => {
                const isChecked = e.target.checked;
                // Find *only visible* items
                newListEl.querySelectorAll('.attendance-course-item').forEach(item => {
                    if (item.style.display !== 'none') {
                        const checkbox = item.querySelector('.form-check-input:not(:disabled)');
                        if (checkbox) {
                            checkbox.checked = isChecked;
                        }
                    }
                });
                updateAttendanceCounts();
            });
        }
        // --- End of Toggle Logic ---

        // Update modal title, description, and counts
        courseCountEl.textContent = `Total: ${courses.length}`;
        
        if (missingCoursesFound) {
            modalTitle.innerHTML = '<i class="fa-solid fa-clipboard-user me-2"></i>Import Missing Courses';
            modalDescription.textContent = 'The following courses were found in the Attendance System but not in your main LMS results. Select courses to import and set their credit hours.';
        } else {
            modalTitle.innerHTML = '<i class="fa-solid fa-clipboard-check me-2"></i>Courses Synced';
            modalDescription.textContent = 'All courses found in the Attendance System are already present in your LMS results. You can toggle "Show All" to review them.';
        }

        importAttendanceCoursesBtn.disabled = false;
        updateAttendanceCounts(); // Set initial state for counts and 'Select All'
    }


     function importSelectedAttendanceCourses() {
        importedAttendanceCourses = []; // Clear any previous import list
        const selectedCheckboxes = document.querySelectorAll('#attendanceCourseList .form-check-input:checked');
        let importedCount = 0;

        selectedCheckboxes.forEach(checkbox => {
            // Ensure we are not importing a disabled checkbox
            if (checkbox.disabled) return;

            const courseData = JSON.parse(checkbox.dataset.courseData);
            const index = checkbox.value;
            const creditHoursSelect = document.getElementById(`att-ch-${index}`);
            const creditHours = parseInt(creditHoursSelect.value);

            if (!isNaN(creditHours) && creditHours > 0 && creditHours <= 10) {
                const semesterName = courseData.semester; // This is already the normalized name

                // Ensure semester exists
                if (!processedData.semesters[semesterName]) {
                    processedData.semesters[semesterName] = {
                        originalName: semesterName, // Use the processed name
                        sortKey: getSemesterOrderKey(semesterName),
                        courses: []
                    };
                     addStatusMessage(`Created new semester entry: ${semesterName} during import`, 'info');
                }

                // Create the course object
                const marks = courseData.marks;
                const grade = calculateCustomGrade(marks, creditHours); // Recalculate grade based on CH
                const qualityPoints = calculateQualityPoints(marks, creditHours, grade); // Use 'grade'

                const newCourse = {
                    code: courseData.code,
                    title: courseData.title || 'Imported from Attendance',
                    creditHours: creditHours,
                    creditHoursDisplay: `${creditHours}(${creditHours}-0)`, // Assuming theory only
                    marks: marks,
                    qualityPoints: qualityPoints,
                    grade: grade, 
                    teacher: courseData.teacher || 'Attendance System',
                    mid: courseData.mid || 'N/A',
                    assignment: courseData.assignment || 'N/A',
                    final: courseData.final || 'N/A',
                    practical: courseData.practical || 'N/A',
                    total: marks,
                    isExtraEnrolled: false, // Will be recalculated
                    isRepeated: false,      // Will be recalculated
                    isDeleted: false,
                    isCustom: true,          // Mark as custom
                    source: 'attendance',    // Add source marker
                    originalSemester: semesterName // Add originalSemester
                };

                 // Check if it already exists (non-deleted) before adding
                const semester = processedData.semesters[semesterName];
                 if (!semester.courses.some(c => !c.isDeleted && c.code.toUpperCase() === newCourse.code)) {
                     semester.courses.push(newCourse);
                     // Add to our revert list
                     importedAttendanceCourses.push({ semester: semesterName, code: newCourse.code });
                     importedCount++;
                 } else {
                     addStatusMessage(`Skipped importing ${newCourse.code} for ${semesterName} as it already exists.`, 'warning');
                 }

            } else {
                 showToast(`Invalid Credit Hours selected for ${courseData.code}`, 'warning');
            }
        });

        if (importedCount > 0) {
            recalculateAndDisplay(); // This will save the profile
            showToast(`${importedCount} course(s) imported successfully!`, 'success');
            addStatusMessage(`Imported ${importedCount} courses from Attendance System.`, 'info');
        } else {
              showToast('No new courses were imported.', 'info');
              importedAttendanceCourses = []; // Ensure list is empty if nothing was imported
        }

        setupAttendanceButton(); // Update the button to "Revert" or "Attendance"
        attendanceImportModal.hide();
    }



      async function fetchResult() {
        const regNum = registrationNumber.value.trim();
        if (!regNum) { showToast('Please enter a registration number', 'error'); return; }

        resultContainer.style.display = 'none';
        document.getElementById('bedResultContainer').style.display = 'none'; // --- NEW: Hide B.Ed. container
        showLoadingStage('connecting');
        addStatusMessage(`Fetching result for: ${regNum}`, 'info');
        semesterResults.innerHTML = '';
        gpaChartContainer.style.display = 'none';

        try {
          const response = await fetch(`${API_ENDPOINT}&registrationNumber=${encodeURIComponent(regNum)}`);
          showLoadingStage('fetching');
          const data = await response.json();

          if (!response.ok || !data.success) {
            throw new Error(data.message || `Server responded with status ${response.status}`);
          }

          showLoadingStage('processing');

          if (data.resultData && data.resultData.length > 0) {
            addStatusMessage('Result fetched successfully from UAF LMS', 'success');
            isInitialLoad = true;
            const processed = processScrapedData(data); // This now contains `hasBedCourses`

            // --- NEW B.Ed. Logic ---
            if (processed.hasBedCourses) {
              // Show the modal and attach handlers
              document.getElementById('bedConfirmYes').onclick = () => handleBedConfirm(true, processed);
              document.getElementById('bedConfirmNo').onclick = () => handleBedConfirm(false, processed);
              if (bedConfirmationModal) bedConfirmationModal.show();
            } else {
              // No B.Ed. courses, proceed as normal
              handleBedConfirm(false, processed);
            }
            // --- End of NEW B.Ed. Logic ---

          } else {
            // Even if success is true, resultData might be empty
             throw new Error("No result records found for this registration number.");
          }
        } catch (error) {
            console.error("Fetch Error:", error);
            let userMessage, logMessage;

            if (error instanceof TypeError && error.message.includes('Failed to fetch')) {
                userMessage = 'Network error. Please check your internet connection.';
                logMessage = 'Failed to fetch due to a network error. Ensure you are connected to the internet.';
            } else {
                 userMessage = `Could not retrieve results: ${error.message}`; // Use error message from backend or default
                 logMessage = `API/LMS Error: ${error.message}`;
            }

            addStatusMessage(logMessage, 'error');
            showToast(userMessage, 'error');
            showLoadingStage(null);
        }
      }

      // --- UPDATE: Event Listener for main export button opens manager ---
      exportProfilesBtn.addEventListener('click', () => {
        if (Object.keys(getProfiles()).length === 0) {
            showToast('No profiles available to export.', 'info');
            return;
        }
        renderProfileManager();
        profileManagerModal.show();
        showToast('Select profiles from the manager to export.', 'info');
      });

      // Event Listeners
      resultForm.addEventListener('submit', (e) => { e.preventDefault(); fetchResult(); });
      downloadLogBtn.addEventListener('click', downloadLog);
      clearLogBtn.addEventListener('click', clearLog);
      saveCourseBtn.addEventListener('click', addCustomCourse);
      profileSwitcher.addEventListener('change', switchProfile);
      
      // FIX: Add the missing event listener here
      saveProfileNameBtn.addEventListener('click', renameProfile); 
      
      document.getElementById('confirmationConfirmBtn').addEventListener('click', handleConfirm);

      // Main buttons
      downloadPdfBtn.addEventListener('click', generatePDF);
      addForecastSemesterBtn.addEventListener('click', addForecastSemester);

      // B.Ed. Tab buttons
      document.getElementById('bed-downloadPdfBtn').addEventListener('click', generatePDF);
      document.getElementById('bed-addForecastSemesterBtn').addEventListener('click', addForecastSemester);
      
      // Other Tab buttons
      document.getElementById('other-downloadPdfBtn').addEventListener('click', generatePDF);
      document.getElementById('other-addForecastSemesterBtn').addEventListener('click', addForecastSemester);

       // NEW: Attendance Button Setup
      setupAttendanceButton(); // This replaces the simple event listener
      importAttendanceCoursesBtn.addEventListener('click', importSelectedAttendanceCourses);

      importProfilesBtn.addEventListener('click', importProfiles);
      importProfilesBtnModal.addEventListener('click', importProfiles); // Add listener for modal button
      exportProfilesBtnModal.addEventListener('click', exportSelectedProfiles); // Use exportSelectedProfiles for modal button

      // Profile Manager Listeners
      openProfileManagerBtn.addEventListener('click', () => {
          renderProfileManager();
          profileManagerModal.show();
      });
      document.getElementById('selectAllProfiles').addEventListener('change', e => {
          document.querySelectorAll('.profile-checkbox').forEach(cb => cb.checked = e.target.checked);
          const anyChecked = e.target.checked;
           document.getElementById('bulkActionsBtn').disabled = !anyChecked;
           exportProfilesBtnModal.disabled = !anyChecked; // Also enable/disable export in modal
      });

        document.getElementById('profileManagerList').addEventListener('change', e => {
            if (e.target.classList.contains('profile-checkbox')) {
                const anyChecked = !!document.querySelector('.profile-checkbox:checked');
                document.getElementById('bulkActionsBtn').disabled = !anyChecked;
                // Also enable/disable the modal export button based on selection
                exportProfilesBtnModal.disabled = !anyChecked;

                 // Update "Select All" checkbox state
                const allCheckboxes = document.querySelectorAll('.profile-checkbox');
                const allChecked = allCheckboxes.length > 0 && Array.from(allCheckboxes).every(cb => cb.checked);
                document.getElementById('selectAllProfiles').checked = allChecked;
                document.getElementById('selectAllProfiles').indeterminate = !allChecked && anyChecked;

            }
        });

      document.getElementById('deleteSelectedBtn').addEventListener('click', handleBulkAction);

      init();
    });







document.addEventListener('DOMContentLoaded', function() {

  // --- Common Elements ---
  const qpTableContainer = document.getElementById('qpTableContainer');
  const qpTableImage = document.getElementById('qpTableImage');
  const lightbox = document.getElementById('imageLightbox');
  const lightboxContent = document.getElementById('lightboxContent');
  const lightboxClose = document.getElementById('lightboxClose');

  if (!qpTableContainer || !qpTableImage || !lightbox || !lightboxContent || !lightboxClose) {
      console.error("Lightbox elements not found!");
      return;
  }

  const imageSrc = qpTableImage.src;
  let lightboxImage = null; // Reference to the image inside the lightbox

  // --- State Variables ---
  let isLightboxOpen = false;
  let isDesktop = window.matchMedia("(hover: hover) and (pointer: fine)").matches; // Detect if likely desktop

  // Mobile pinch/pan state
  let scale = 1, isPanning = false, isPinching = false;
  let start = { x: 0, y: 0 };
  let initialPinchDistance = 0;
  let currentTransform = { scale: 1, translateX: 0, translateY: 0 };

  // Desktop hover zoom state
  const desktopZoomLevel = 4.5; // How much to zoom on desktop hover

  // --- Utility Functions ---
  function applyTransform() {
    if (!lightboxImage) return;
    // Apply transform based on *current* state (pan/zoom for mobile)
    lightboxImage.style.transform = `translate(${currentTransform.translateX}px, ${currentTransform.translateY}px) scale(${currentTransform.scale})`;
  }

  function getDistance(p1, p2) {
    return Math.hypot(p1.clientX - p2.clientX, p1.clientY - p2.clientY);
  }

  function getCenter(p1, p2) {
    return { x: (p1.clientX + p2.clientX) / 2, y: (p1.clientY + p2.clientY) / 2 };
  }

  // --- Lightbox Open/Close ---
  function openLightbox() {
    if (isLightboxOpen) return;

    const imgClone = qpTableImage.cloneNode(true);
    imgClone.id = 'lightboxImage';
    // Reset styles specifically for the lightbox
    imgClone.style.transform = '';
    imgClone.style.transition = 'transform 0.15s ease-out'; // Keep transition
    imgClone.style.maxWidth = '95%';
    imgClone.style.maxHeight = '95%';
    imgClone.style.width = 'auto';
    imgClone.style.height = 'auto';
    lightboxContent.innerHTML = '';
    lightboxContent.appendChild(imgClone);
    lightboxImage = imgClone;

    // Reset interaction states
    isPanning = false; isPinching = false;
    currentTransform = { scale: 1, translateX: 0, translateY: 0 };
    applyTransform(); // Set initial state

    lightbox.classList.add('show');
    document.body.style.overflow = 'hidden'; // Prevent body scroll
    isLightboxOpen = true;

    // Attach interaction listeners based on device type
    if (isDesktop) {
        setupDesktopLightboxInteraction();
    } else {
        setupMobileLightboxInteraction();
    }
  }

  function closeLightbox() {
    if (!isLightboxOpen) return;
    lightbox.classList.remove('show');
    document.body.style.overflow = ''; // Restore body scroll
    isLightboxOpen = false;
    lightboxImage = null; // Clean up image ref
    // Remove specific listeners added when opened
    removeDesktopLightboxInteraction();
    removeMobileLightboxInteraction();
  }

  // --- Desktop Lightbox Interaction (Hover Zoom) ---
  const handleDesktopMouseMove = (e) => {
      if (!lightboxImage || !isLightboxOpen) return;

      const rect = lightboxImage.getBoundingClientRect();
      // Calculate cursor position as a percentage of the image dimensions
      const xPercent = ((e.clientX - rect.left) / rect.width) * 100;
      const yPercent = ((e.clientY - rect.top) / rect.height) * 100;

      // Apply scale and set transform origin to follow cursor
      lightboxImage.style.transformOrigin = `${xPercent}% ${yPercent}%`;
      lightboxImage.style.transform = `scale(${desktopZoomLevel})`;
  };

  const handleDesktopMouseLeave = () => {
      if (!lightboxImage || !isLightboxOpen) return;
      // Reset zoom when mouse leaves the image
      lightboxImage.style.transformOrigin = `center center`;
      lightboxImage.style.transform = `scale(1)`;
  };

  function setupDesktopLightboxInteraction() {
    if (!lightboxImage) return;
    lightboxContent.classList.add('desktop-zoom-active');
    lightboxImage.addEventListener('mousemove', handleDesktopMouseMove);
    lightboxImage.addEventListener('mouseleave', handleDesktopMouseLeave);
     // Add wheel zoom for desktop as well
    lightboxContent.addEventListener('wheel', handleWheelZoom, { passive: false });
  }

  function removeDesktopLightboxInteraction() {
    if (!lightboxImage) return;
    lightboxContent.classList.remove('desktop-zoom-active');
    lightboxImage.removeEventListener('mousemove', handleDesktopMouseMove);
    lightboxImage.removeEventListener('mouseleave', handleDesktopMouseLeave);
    lightboxContent.removeEventListener('wheel', handleWheelZoom);
  }

  // --- Mobile Lightbox Interaction (Pinch/Pan) ---
  const handleTouchStart = (e) => {
    if (!lightboxImage || !isLightboxOpen) return;
    
    if (e.touches.length === 1 && currentTransform.scale > 1) { // Only pan if zoomed
      isPanning = true;
      start.x = e.touches[0].clientX - currentTransform.translateX;
      start.y = e.touches[0].clientY - currentTransform.translateY;
    } else if (e.touches.length === 2) {
      isPanning = false; // Stop panning
      isPinching = true;
      initialPinchDistance = getDistance(e.touches[0], e.touches[1]);
      // Store center based on current transform - needed? Maybe not.
    }
  };

  const handleTouchMove = (e) => {
    if (!lightboxImage || !isLightboxOpen) return;
    e.preventDefault(); // Prevent scroll

    if (isPanning && e.touches.length === 1) {
      currentTransform.translateX = e.touches[0].clientX - start.x;
      currentTransform.translateY = e.touches[0].clientY - start.y;
      applyTransform();
    } else if (isPinching && e.touches.length === 2) {
        const currentPinchDistance = getDistance(e.touches[0], e.touches[1]);
        const scaleChange = currentPinchDistance / initialPinchDistance;
        let potentialNewScale = currentTransform.scale * scaleChange;

        // Clamp scale
        potentialNewScale = Math.max(1, Math.min(potentialNewScale, 10)); // Min 1x, Max 10x

        // Calculate zoom origin relative to the image
        const rect = lightboxImage.getBoundingClientRect();
        // Use the initial touch center relative to the viewport
        const touchCenterXVP = getCenter(e.touches[0], e.touches[1]).x;
        const touchCenterYVP = getCenter(e.touches[0], e.touches[1]).y;
        // Convert to position relative to the *untransformed* image top-left
        const originX = (touchCenterXVP - rect.left - currentTransform.translateX) / currentTransform.scale;
        const originY = (touchCenterYVP - rect.top - currentTransform.translateY) / currentTransform.scale;

        // Calculate new translation to keep origin point fixed
        currentTransform.translateX += originX * currentTransform.scale - originX * potentialNewScale;
        currentTransform.translateY += originY * currentTransform.scale - originY * potentialNewScale;
        currentTransform.scale = potentialNewScale; // Apply the new scale

        applyTransform();

        // Update for next move event (essential)
        initialPinchDistance = currentPinchDistance;
    }
  };

  const handleTouchEnd = (e) => {
    if (!lightboxImage || !isLightboxOpen) return;

    if (isPanning && e.touches.length === 0) {
      isPanning = false;
    }
    if (isPinching && e.touches.length < 2) {
      isPinching = false;
      // Check if scale is close to 1, if so, reset position
      if (currentTransform.scale <= 1.05) {
         currentTransform.scale = 1; // Snap to 1
         currentTransform.translateX = 0;
         currentTransform.translateY = 0;
         // Apply transform with a slight delay/transition if desired
         lightboxImage.style.transition = 'transform 0.2s ease-out'; // Add smooth reset
         applyTransform();
         setTimeout(() => {
              if (lightboxImage) lightboxImage.style.transition = 'transform 0.15s ease-out'; // Restore default transition
         }, 200);
      }
    }
  };

  function setupMobileLightboxInteraction() {
    if (!lightboxContent) return;
    lightboxContent.addEventListener('touchstart', handleTouchStart, { passive: false });
    lightboxContent.addEventListener('touchmove', handleTouchMove, { passive: false });
    lightboxContent.addEventListener('touchend', handleTouchEnd);
    lightboxContent.addEventListener('touchcancel', handleTouchEnd); // Use same handler for cancel
  }

  function removeMobileLightboxInteraction() {
    if (!lightboxContent) return;
    lightboxContent.removeEventListener('touchstart', handleTouchStart);
    lightboxContent.removeEventListener('touchmove', handleTouchMove);
    lightboxContent.removeEventListener('touchend', handleTouchEnd);
    lightboxContent.removeEventListener('touchcancel', handleTouchEnd);
  }

  // --- Wheel Zoom (Common for both in Lightbox) ---
  const handleWheelZoom = (e) => {
      if (!lightboxImage || !isLightboxOpen) return;
      e.preventDefault();

      const rect = lightboxImage.getBoundingClientRect();
      const delta = e.deltaY > 0 ? -0.2 : 0.2; // Zoom speed
      let potentialNewScale = currentTransform.scale + delta * currentTransform.scale; // Zoom relative to current scale

      // Clamp scale
      potentialNewScale = Math.max(1, Math.min(potentialNewScale, 10));

      // Calculate zoom origin relative to image
      const originX = (e.clientX - rect.left - currentTransform.translateX) / currentTransform.scale;
      const originY = (e.clientY - rect.top - currentTransform.translateY) / currentTransform.scale;

      // Calculate new translation to keep origin fixed
      currentTransform.translateX += originX * currentTransform.scale - originX * potentialNewScale;
      currentTransform.translateY += originY * currentTransform.scale - originY * potentialNewScale;
      currentTransform.scale = potentialNewScale;

      // Reset position if zoomed out fully
      if (currentTransform.scale <= 1.05) {
          currentTransform.scale = 1;
          currentTransform.translateX = 0;
          currentTransform.translateY = 0;
      }

      applyTransform();
  };


  // --- Event Listeners ---
  qpTableContainer.addEventListener('click', openLightbox);
  lightboxClose.addEventListener('click', closeLightbox);
  lightbox.addEventListener('click', (e) => { // Close on background click
    if (e.target === lightbox) closeLightbox();
  });

});









document.addEventListener('DOMContentLoaded', function() {
  
  // Initialize Bootstrap Popovers
  const popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
  const popoverList = popoverTriggerList.map(function (popoverTriggerEl) {
    return new bootstrap.Popover(popoverTriggerEl);
  });

  /**
   * Fetches the server statuses from our *own* backend API.
   */
  async function checkServerStatuses() {
    const lmsItem = document.getElementById('lms-status-item');
    const attndItem = document.getElementById('attnd-status-item');
    const lmsDot = document.getElementById('lms-status-dot');
    const attndDot = document.getElementById('attnd-status-dot');

    if (!lmsItem || !attndItem || !lmsDot || !attndDot) return;

    // Loading state is handled by default HTML (infinity-loader is visible)

    try {
      // Call our API endpoint
      const response = await fetch('/api/result-scraper?action=check_status', {
        cache: 'no-cache',
        signal: AbortSignal.timeout(15000) // 15-second timeout
      });
      
      if (!response.ok) {
        throw new Error('Status check API failed');
      }

      const data = await response.json();

      // --- Set LMS status ---
      if (data.lms_status === 'online') {
        lmsDot.className = 'status-dot online';
        lmsDot.title = 'LMS is Online';
      } else {
        // Treat "offline" and "error" both as 'offline' (red)
        lmsDot.className = 'status-dot offline';
        lmsDot.title = 'LMS is Offline or Unreachable';
      }
      // Add 'status-loaded' class to show the label and dot
      lmsItem.classList.add('status-loaded');


      // --- Set Attendance status ---
      if (data.attnd_status === 'online') {
        attndDot.className = 'status-dot online';
        attndDot.title = 'Attendance System is Online';
      } else {
        // Treat "offline" and "error" both as 'offline' (red)
        attndDot.className = 'status-dot offline';
        attndDot.title = 'Attendance System is Offline or has an Error';
      }
      // Add 'status-loaded' class to show the label and dot
      attndItem.classList.add('status-loaded');

    } catch (error) {
      console.error('Failed to fetch server statuses:', error.name, error.message);
      
      // If the API call itself fails, mark both as offline
      lmsDot.className = 'status-dot offline';
      lmsDot.title = 'Status check failed';
      lmsItem.classList.add('status-loaded');

      attndDot.className = 'status-dot offline';
      attndDot.title = 'Status check failed';
      attndItem.classList.add('status-loaded');
    }
  }

  // Run the check when the page loads
  checkServerStatuses();
  
});
