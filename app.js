/* eosguide app logic
   Source of truth for UI behaviors: filters, categories, saved items, share, mobile nav.
   This file is loaded by index.html using <script defer src="app.js"></script>
*/
// Categories for the filter buttons
    const categories = [
      { key: 'all', name: 'All Opportunities', icon: '✨', color: 'from-cyan-600 to-blue-600', description: 'Browse all available opportunities' },
      { key: 'saved', name: 'My Saved', icon: '🔖', color: 'from-pink-600 to-rose-600', description: 'Opportunities you\'ve bookmarked' },
      { key: 'ending', name: 'Ending Soon', icon: '⏰', color: 'from-orange-600 to-red-600', description: 'Deadlines within 30 days' }
    ];

    let opportunities = [];
    let currentCategory = 'all';
    let currentSearch = '';
    let categoriesExpanded = false;
    let savedOpportunities = JSON.parse(localStorage.getItem('eosguide-saved') || '[]');

    function calculateDaysLeft(deadlineStr) {
      if (!deadlineStr) return -1;
      const raw = String(deadlineStr).trim();
      if (!raw) return -1;
      const lower = raw.toLowerCase();
      if (['ongoing','none','n/a','na'].includes(lower)) return 999;
      if (lower.includes('rolling') || lower.includes('varies') || lower.includes('tbd')) return 999;

      const parsedMs = Date.parse(raw);
      if (!Number.isNaN(parsedMs)) {
        const deadlineDate = new Date(parsedMs);
        const today = new Date();
        deadlineDate.setHours(0,0,0,0);
        today.setHours(0,0,0,0);
        const diffMs = deadlineDate - today;
        return Math.round(diffMs / (1000 * 60 * 60 * 24));
      }

      const parts = raw.split('/');
      if (parts.length !== 3) return -1;

      const month = parseInt(parts[0], 10);
      const day = parseInt(parts[1], 10);
      const year = parseInt(parts[2], 10);
      if (!month || !day || !year) return -1;

      const deadlineDate = new Date(year, month - 1, day);
      const today = new Date();
      deadlineDate.setHours(0,0,0,0);
      today.setHours(0,0,0,0);
      const diffMs = deadlineDate - today;
      return Math.round(diffMs / (1000 * 60 * 60 * 24));
    }

    async function loadOpportunities() {
      try {
        const response = await fetch('/data/opportunities.json');
        if (!response.ok) throw new Error('Failed to load opportunities');

        const data = await response.json();
        opportunities = data.map(opp => ({
          id: opp.id || opp.title,
          title: opp.title,
          url: opp.url,
          category: opp.category,
          program_type: opp.program_type || opp.category,
          geography: opp.state === 'Nationwide' ? 'national' : 'state',
          who_qualifies: opp.description,
          description: opp.description,
          how_to_apply: 'Visit official link',
          deadline: opp.deadline,
          daysLeft: opp.urgencyDays || calculateDaysLeft(opp.deadline),
          proof_required: opp.proofRequired || opp.proof_required || 'Unknown',
          amount: opp.amount,
          source: opp.url,
          state: opp.state,
          difficulty: opp.difficulty || 'Medium',
          value: opp.value || 'fair',
          featured: opp.featured || false,
          urgencyDays: opp.urgencyDays
        }));

        renderOpportunities();
        updateStateDropdownCounts();
      } catch (error) {
        console.error('Error loading opportunities:', error);
        document.getElementById('opportunitiesGrid').innerHTML = `
          <div class="text-center py-12">
            <p class="text-gray-600">Unable to load opportunities. Please try again later.</p>
          </div>
        `;
      }
    }

    const stateMapping = {
      'AL':'Alabama','AK':'Alaska','AZ':'Arizona','AR':'Arkansas','CA':'California','CO':'Colorado','CT':'Connecticut','DE':'Delaware',
      'FL':'Florida','GA':'Georgia','HI':'Hawaii','ID':'Idaho','IL':'Illinois','IN':'Indiana','IA':'Iowa','KS':'Kansas','KY':'Kentucky',
      'LA':'Louisiana','ME':'Maine','MD':'Maryland','MA':'Massachusetts','MI':'Michigan','MN':'Minnesota','MS':'Mississippi','MO':'Missouri',
      'MT':'Montana','NE':'Nebraska','NV':'Nevada','NH':'New Hampshire','NJ':'New Jersey','NM':'New Mexico','NY':'New York','NC':'North Carolina',
      'ND':'North Dakota','OH':'Ohio','OK':'Oklahoma','OR':'Oregon','PA':'Pennsylvania','RI':'Rhode Island','SC':'South Carolina','SD':'South Dakota',
      'TN':'Tennessee','TX':'Texas','UT':'Utah','VT':'Vermont','VA':'Virginia','WA':'Washington','WV':'West Virginia','WI':'Wisconsin','WY':'Wyoming',
      'DC':'District of Columbia'
    };

    function updateStateDropdownCounts() {
      const stateSelector = document.getElementById('stateSelector');
      if (!stateSelector) return;

      let nationwideCount = 0;
      opportunities.forEach(opp => { if (opp.state === 'Nationwide') nationwideCount++; });

      Array.from(stateSelector.options).forEach(option => {
        const value = option.value;
        if (value === '') {
          option.textContent = `All States (${opportunities.length})`;
        } else if (value === 'Nationwide') {
          option.textContent = `Nationwide Only (${nationwideCount})`;
        } else {
          const fullStateName = stateMapping[value];
          let stateSpecificCount = 0;
          opportunities.forEach(opp => {
            if (opp.state === value || opp.state === fullStateName) stateSpecificCount++;
          });
          option.textContent = `${fullStateName} (${stateSpecificCount})`;
        }
      });
    }

    function renderCategories() {
      const grid = document.getElementById('categoriesGrid');
      const visible = categoriesExpanded ? categories : categories.slice(0, 6);

      grid.innerHTML = visible.map((cat, idx) => `
        <button onclick="filterCategory('${cat.key}')"
          class="category-btn animate-fadeInUp delay-${idx * 50} p-3 rounded-2xl transition-all duration-300 hover:scale-105 group text-left ${currentCategory === cat.key ? 'bg-white shadow-xl ring-2 ring-purple-500' : 'bg-white/70 hover:bg-white hover:shadow-lg'}"
          data-category="${cat.key}">
          <div class="text-3xl mb-1 group-hover:scale-110 transition-transform duration-300">${cat.icon}</div>
          <div class="text-xs font-bold bg-gradient-to-r ${cat.color} bg-clip-text text-transparent leading-tight">${cat.name}</div>
        </button>
      `).join('');

      document.getElementById('toggleText').textContent = categoriesExpanded ? 'Show Less' : 'Show All';
      document.getElementById('toggleIcon').style.transform = categoriesExpanded ? 'rotate(180deg)' : 'rotate(0deg)';
    }

    function toggleCategories() {
      categoriesExpanded = !categoriesExpanded;
      renderCategories();
    }

    function toggleSaved(oppId) {
      if (savedOpportunities.includes(oppId)) {
        savedOpportunities = savedOpportunities.filter(id => id !== oppId);
      } else {
        savedOpportunities.push(oppId);
      }
      localStorage.setItem('eosguide-saved', JSON.stringify(savedOpportunities));
      renderOpportunities();
    }

    function getUrgencyBadge(urgencyDays, daysLeft) {
      const days = urgencyDays || daysLeft;
      if (!days || days < 0 || days > 900) return '';

      if (days <= 7) {
        return `<div class="flex items-center space-x-1 px-3 py-1 bg-gradient-to-r from-red-500 to-pink-500 text-white rounded-full text-xs font-bold animate-pulse">
          <span>🔥 ${days}d left</span>
        </div>`;
      } else if (days <= 30) {
        return `<div class="flex items-center space-x-1 px-3 py-1 bg-gradient-to-r from-orange-500 to-red-500 text-white rounded-full text-xs font-bold">
          <span>⏰ ${days}d left</span>
        </div>`;
      } else if (days <= 60) {
        return `<div class="flex items-center space-x-1 px-2 py-1 bg-yellow-100 text-yellow-700 rounded-full text-xs font-bold">
          <span>📅 ${days}d</span>
        </div>`;
      }
      return '';
    }

    function getValueBadge(value, featured) {
      if (featured) return '<span class="px-3 py-1 bg-gradient-to-r from-purple-100 to-pink-100 text-purple-700 rounded-full text-xs font-bold border-2 border-purple-300">⭐ FEATURED</span>';
      if (value === 'excellent') return '<span class="px-3 py-1 bg-green-100 text-green-700 rounded-full text-xs font-bold">⭐ EXCELLENT</span>';
      if (value === 'good') return '<span class="px-3 py-1 bg-blue-100 text-blue-700 rounded-full text-xs font-bold">✓ GOOD</span>';
      if (value === 'fair') return '<span class="px-3 py-1 bg-yellow-100 text-yellow-700 rounded-full text-xs font-bold">~ FAIR</span>';
      return '';
    }

    function formatDeadline(deadline) {
      if (!deadline) return 'No deadline';
      try {
        const date = new Date(deadline);
        return date.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });
      } catch {
        return deadline;
      }
    }

    function renderOpportunities() {
      const grid = document.getElementById('opportunitiesGrid');
      const noResults = document.getElementById('noResults');
      const oppCount = document.getElementById('oppCount');
      const categoryInfo = document.getElementById('categoryInfo');
      const stateSelector = document.getElementById('stateSelector');
      const selectedState = stateSelector ? stateSelector.value : '';

      const filtered = opportunities.filter(opp => {
        let matchesState = true;

        if (selectedState && selectedState !== '') {
          if (selectedState === 'Nationwide') {
            matchesState = opp.state === 'Nationwide';
          } else {
            const fullStateName = stateMapping[selectedState];
            matchesState =
              opp.state === 'Nationwide' ||
              opp.state === selectedState ||
              opp.state === fullStateName;
          }
        }

        const matchesCategory =
          currentCategory === 'all' ||
          (currentCategory === 'saved' ? savedOpportunities.includes(opp.id) : false) ||
          (currentCategory === 'ending' && opp.daysLeft < 30 && opp.daysLeft > 0) ||
          (currentCategory === 'national' && opp.geography === 'national') ||
          opp.category === currentCategory;

        const matchesSearch =
          opp.title.toLowerCase().includes(currentSearch.toLowerCase()) ||
          (opp.description || '').toLowerCase().includes(currentSearch.toLowerCase());

        return matchesState && matchesCategory && matchesSearch;
      });

      filtered.sort((a, b) => {
        if (a.featured && !b.featured) return -1;
        if (!a.featured && b.featured) return 1;
        const aDays = a.daysLeft || 999;
        const bDays = b.daysLeft || 999;
        return aDays - bDays;
      });

      oppCount.textContent = `(${filtered.length})`;

      if (currentCategory !== 'all') {
        const catInfo = categories.find(c => c.key === currentCategory);
        if (catInfo) {
          categoryInfo.classList.remove('hidden');
          document.getElementById('catIcon').textContent = catInfo.icon;
          document.getElementById('catName').textContent = catInfo.name;
          document.getElementById('catDesc').textContent = catInfo.description;
        }
      } else {
        categoryInfo.classList.add('hidden');
      }

      if (filtered.length === 0) {
        grid.innerHTML = '';
        noResults.classList.remove('hidden');
        document.getElementById('noResultsIcon').textContent = currentCategory === 'saved' ? '🔖' : '🔍';
        document.getElementById('noResultsTitle').textContent = currentCategory === 'saved' ? 'No saved opportunities yet' : 'No opportunities found';
        document.getElementById('noResultsText').textContent = currentCategory === 'saved'
          ? 'Start saving opportunities to access them quickly later'
          : 'Try adjusting your search or filters';
        return;
      }

      noResults.classList.add('hidden');

      grid.innerHTML = filtered.map((opp, index) => {
        const catInfo = categories.find(c => c.key === opp.category) || { icon: '📋', name: opp.category };
        const isSaved = savedOpportunities.includes(opp.id);

        return `
          <div class="animate-fadeInUp delay-${Math.min(index, 5) * 100} group bg-white rounded-3xl p-6 shadow-lg hover:shadow-2xl transition-all duration-300 hover:-translate-y-2 relative overflow-hidden">
            <div class="absolute inset-0 bg-gradient-to-br from-purple-500/0 to-pink-500/0 group-hover:from-purple-500/5 group-hover:to-pink-500/5 transition-all duration-300 rounded-3xl"></div>

            <div class="relative">
              <!-- FIX: pin save icon so long badges don't push it offscreen -->
              <div class="relative mb-3 pr-12">
                <div class="flex flex-wrap gap-2 mb-2">
                  ${opp.featured || opp.value ? getValueBadge(opp.value, opp.featured) : ''}
                  <div class="inline-flex items-center space-x-1 px-3 py-1 bg-gradient-to-r from-gray-100 to-gray-200 rounded-full text-xs font-bold text-gray-700">
                    <span>${catInfo.icon}</span>
                    <span class="truncate">${catInfo.name}</span>
                  </div>
                  ${opp.geography === 'national' ? `
                    <div class="inline-flex items-center space-x-1 px-2 py-1 rounded-full bg-blue-50 text-[10px] font-semibold text-blue-700 border border-blue-100">
                      <span aria-hidden="true">🌐</span>
                      <span>Nationwide</span>
                    </div>
                  ` : ''}
                </div>

                <button type="button"
                        onclick="toggleSaved('${opp.id}')"
                        class="absolute top-0 right-0 p-2 hover:bg-purple-50 rounded-full transition-colors"
                        title="${isSaved ? 'Remove from saved' : 'Save for later'}"
                        aria-label="${isSaved ? 'Unsave' : 'Save'}">
                  ${isSaved
                    ? '<svg class="w-5 h-5 text-purple-600 fill-purple-600" fill="currentColor" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 5a2 2 0 012-2h10a2 2 0 012 2v16l-7-3.5L5 21V5z"></path></svg>'
                    : '<svg class="w-5 h-5 text-gray-400 group-hover:text-purple-600 transition-colors" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 5a2 2 0 012-2h10a2 2 0 012 2v16l-7-3.5L5 21V5z"></path></svg>'
                  }
                </button>
              </div>

              <div class="flex items-center justify-between mb-3">
                <div class="flex items-center space-x-2">
                  ${getUrgencyBadge(opp.urgencyDays, opp.daysLeft)}
                </div>
                <div class="flex items-center space-x-1 text-green-600">
                  <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
                  <span class="font-black text-sm">${opp.amount || ''}</span>
                </div>
              </div>

              <h4 class="text-lg font-bold text-gray-900 mb-2 line-clamp-2 group-hover:text-purple-600 transition-colors duration-300">${opp.title || ''}</h4>
              <p class="text-sm text-gray-600 mb-4 line-clamp-2 font-light">${opp.description || ''}</p>

              <div class="space-y-2 mb-4">
                <div class="flex items-center justify-between text-sm">
                  <span class="text-gray-600 font-normal">Deadline:</span>
                  <span class="font-bold text-gray-900">${formatDeadline(opp.deadline)}</span>
                </div>
                <div class="flex items-center justify-between text-sm">
                  <span class="text-gray-600 font-normal">Difficulty:</span>
                  <span class="px-3 py-1 rounded-full text-xs font-bold ${
                    opp.difficulty === 'Easy' ? 'bg-green-100 text-green-700' :
                    opp.difficulty === 'Hard' ? 'bg-red-100 text-red-700' :
                    'bg-yellow-100 text-yellow-700'
                  }">${opp.difficulty || 'Medium'}</span>
                </div>
                <div class="flex items-center justify-between text-sm">
                  <span class="text-gray-600 font-normal">Location:</span>
                  <span class="font-bold text-gray-900">${opp.state || ''}</span>
                </div>
              </div>

              <a href="${opp.url}" target="_blank" rel="noopener noreferrer"
                 class="block w-full text-center px-6 py-3 text-white rounded-2xl font-bold hover:shadow-lg hover:scale-105 transition-all duration-300"
                 style="background: linear-gradient(135deg, #FF6B35 0%, #FF8C42 100%);">
                View Details →
              </a>
            </div>
          </div>
        `;
      }).join('');
    }

    function filterCategory(category) {
      if (currentCategory === category && category !== 'all') currentCategory = 'all';
      else currentCategory = category;

      renderCategories();
      renderOpportunities();
    }

    function filterOpportunities() {
      currentSearch = document.getElementById('searchInput').value || '';
      if (currentSearch.trim() !== '') currentCategory = 'all';
      renderCategories();
      renderOpportunities();
    }

    function openNewsletter() {
      const state = document.getElementById('stateSelector')?.value || '';
      document.getElementById('selectedState').textContent = state || 'All States';
      document.getElementById('newsletterModal').classList.remove('hidden');
    }
    function closeNewsletter() {
      document.getElementById('newsletterModal').classList.add('hidden');
    }
    function handleNewsletterSubmit(e) {
      e.preventDefault();
      const email = document.getElementById('emailInput').value;
      alert(`Thanks for subscribing! We'll send updates to ${email}`);
      document.getElementById('emailInput').value = '';
      closeNewsletter();
    }

    const stateSelectorEl = document.getElementById('stateSelector');
    if (stateSelectorEl) {
      stateSelectorEl.addEventListener('change', function () {
        renderOpportunities();
      });
    }

    // Back to top
    const backToTopBtn = document.getElementById('backToTop');
    window.addEventListener('scroll', () => {
      backToTopBtn.style.display = window.scrollY > 400 ? 'block' : 'none';
    });
    backToTopBtn.addEventListener('click', () => {
      window.scrollTo({ top: 0, behavior: 'smooth' });
    });

    // ------- Sharing helpers -------
    function getCurrentShareInfo() {
      const url = window.location.href.split('#')[0];
      const title = document.title || 'eosguide';
      return { url, title };
    }
    function shareCopyPage() {
      const { url } = getCurrentShareInfo();
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(url).then(() => alert('Link copied to clipboard.')).catch(() => alert('Copy failed. You can still copy from the address bar.'));
      } else {
        prompt('Copy this link:', url);
      }
    }
    function shareSmsPage(event) {
      event.preventDefault();
      const { url, title } = getCurrentShareInfo();
      const body = encodeURIComponent(title + ' - ' + url);
      window.location.href = 'sms:?&body=' + body;
    }
    function shareEmailPage(event) {
      event.preventDefault();
      const { url, title } = getCurrentShareInfo();
      const subject = encodeURIComponent(title);
      const body = encodeURIComponent('Thought this might be useful:\n\n' + url);
      window.location.href = 'mailto:?subject=' + subject + '&body=' + body;
    }
    function shareFacebookPage(event) {
      event.preventDefault();
      const { url } = getCurrentShareInfo();
      window.open('https://www.facebook.com/sharer/sharer.php?u=' + encodeURIComponent(url), '_blank');
    }
    function shareRedditPage(event) {
      event.preventDefault();
      const { url, title } = getCurrentShareInfo();
      window.open('https://www.reddit.com/submit?url=' + encodeURIComponent(url) + '&title=' + encodeURIComponent(title), '_blank');
    }

    // ------- Mobile bottom nav helpers -------
    function mobileNavHome() {
      filterCategory('all');
      const search = document.getElementById('searchInput');
      if (search) search.value = '';
      const state = document.getElementById('stateSelector');
      if (state) state.value = '';
      filterOpportunities();
      document.getElementById('home-section')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

    function mobileNavSaved() {
      filterCategory('saved');
      document.getElementById('saved-section')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

    function mobileNavInfo() {
      document.getElementById('info-section')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

    // Initial render
    renderCategories();
    loadOpportunities();
  function initApp() {
    // Hook state dropdown so changing state re-runs the filter
    const stateSelectorEl = document.getElementById('stateSelector');
    if (stateSelectorEl) {
      stateSelectorEl.addEventListener('change', function () {
        renderOpportunities();
      });
    }

    // Back to top
    const backToTopBtn = document.getElementById('backToTop');
    if (backToTopBtn) {
      window.addEventListener('scroll', () => {
        backToTopBtn.style.display = window.scrollY > 400 ? 'block' : 'none';
      });
      backToTopBtn.addEventListener('click', () => {
        window.scrollTo({ top: 0, behavior: 'smooth' });
      });
    }

    renderCategories();
    loadOpportunities();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initApp);
  } else {
    initApp();
  }
