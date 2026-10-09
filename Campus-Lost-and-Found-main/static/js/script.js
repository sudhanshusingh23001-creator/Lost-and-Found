let items = [];
const API = '/api';
let reportModal, detailsModal, lostForm, foundForm;

async function apiFetch(path, options = {}) {
    const res = await fetch(API + path, {
        headers: { 'Content-Type': 'application/json' },
        ...options
    });
    if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(err.detail || 'Request failed');
    }
    return res.json();
}

async function fetchAdminDetails() {
    const blockSelect = document.getElementById('admin_block_select');
    const selectedBlock = blockSelect ? blockSelect.value : '';
    const resultCard = document.getElementById('admin_result_card');

    if (!selectedBlock) {
        alert("Please select a Block first to see the relevant Admin Help Desk!");
        if (resultCard) resultCard.style.display = 'none';
        return;
    }

    try {
        const safeBlock = encodeURIComponent(selectedBlock);
        const adminData = await apiFetch('/admin/' + safeBlock);
        document.getElementById('admin_result_title').innerText = selectedBlock + ' Block — Help Desk';
        document.getElementById('admin_office').innerText = adminData.office_location;
        document.getElementById('admin_contact').innerText = adminData.contact_number;
        document.getElementById('admin_timings').innerText = adminData.timings;
        resultCard.style.display = 'none';
        void resultCard.offsetWidth;
        resultCard.style.display = 'block';
    } catch (err) {
        console.error("Admin Fetch Error:", err);
        alert('Could not fetch admin details: ' + err.message);
        if (resultCard) resultCard.style.display = 'none';
    }
}

window.fetchAdminDetails = fetchAdminDetails;

function openReportForm(type) {
    const modalTitle = document.getElementById('modal_title');
    reportModal.style.display = 'block';

    if (type === 'lost') {
        modalTitle.innerText = 'Report A Lost Item';
        lostForm.style.display = 'block';
        foundForm.style.display = 'none';
    } else {
        modalTitle.innerText = 'Report A Found Item';
        lostForm.style.display = 'none';
        foundForm.style.display = 'block';
    }
}
window.openReportForm = openReportForm;

function closeReportForm() {
    reportModal.style.display = 'none';
    lostForm.reset();
    foundForm.reset();
}
window.closeReportForm = closeReportForm;

function closeDetails() {
    detailsModal.style.display = 'none';
}
window.closeDetails = closeDetails;

async function submitNewReport(event, type) {
    event.preventDefault();

    const activeForm = type === 'lost' ? lostForm : foundForm;
    const formData = new FormData(activeForm);

    const contact = formData.get('reporter_contact') || '';

    const block = formData.get('block_location');
    const room = formData.get('specific_location');
    const fullLocation = block + ' (' + room + ')';

    const dateVal = formData.get('item_date');
    const timeVal = formData.get('item_time');
    const dateReported = dateVal + ' ' + timeVal + ':00';

    const payload = {
        item_name: formData.get('item_name') || '',
        category: (formData.get('category') || 'Other').trim(),
        description: formData.get('description') || '',
        location: fullLocation,
        reporter_name: formData.get('reporter_name') || '',
        reporter_contact: contact,
        item_type: type,
        date_reported: dateReported,
        status: 'active'
    };

    try {
        await apiFetch('/items', {
            method: 'POST',
            body: JSON.stringify(payload)
        });

        alert('Your ' + type + ' item report has been published!');
        closeReportForm();
        await loadItems();
        await loadStats();
    } catch (err) {
        alert('Failed to submit report: ' + err.message);
    }
}
window.submitNewReport = submitNewReport;

async function loadItems() {
    const type = document.getElementById('type_filter').value;
    const category = document.getElementById('category_filter').value;
    const status = document.getElementById('status_filter').value;
    const search = document.getElementById('search_box').value;

    const params = new URLSearchParams();
    if (type) params.append('item_type', type);
    if (category) params.append('category', category);
    if (status) params.append('status', status);
    if (search) params.append('search', search);

    try {
        items = await apiFetch('/items?' + params.toString());
        renderItems(items);
    } catch (err) {
        console.error('Failed to load items:', err);
    }
}

function filterItems() {
    loadItems();
}
window.filterItems = filterItems;

function renderItems(data) {
    if (data === undefined) data = items;
    const itemsDisplay = document.getElementById('items_display');
    const noItemsMsg = document.getElementById('no_items_msg');

    itemsDisplay.innerHTML = '';

    if (!data || data.length === 0) {
        noItemsMsg.style.display = 'block';
        return;
    }

    noItemsMsg.style.display = 'none';

    data.forEach(function (item) {
        var itemCard = document.createElement('div');
        itemCard.className = 'item_card ' + item.item_type;
        itemCard.onclick = function () { openDetails(item.id); };

        var shortDesc = item.description.length > 100
            ? item.description.substring(0, 100) + '...'
            : item.description;

        itemCard.innerHTML =
            '<div class="item_header">' +
            '<span class="item_title">' + item.item_name + '</span>' +
            '<span class="item_badge badge_' + item.item_type + '">' + item.item_type.toUpperCase() + '</span>' +
            '</div>' +
            '<div class="item_category">' + item.category + '</div>' +
            '<p class="item_description">' + shortDesc + '</p>' +
            '<div class="item_info">' +
            '<span>' + item.location + '</span>' +
            '<span>' + item.date_reported + '</span>' +
            '<span>' + item.reporter_name + '</span>' +
            '</div>';

        itemsDisplay.appendChild(itemCard);
    });
}

async function openDetails(id) {
    var item = items.find(function (i) { return i.id === id; });
    if (!item) {
        try {
            item = await apiFetch('/items/' + id);
        } catch (err) {
            alert('Could not load item details.');
            return;
        }
    }

    var dateLabel = item.item_type === 'lost' ? 'Lost' : 'Found';
    var detailsContent = document.getElementById('item_details_content');
    detailsContent.innerHTML =
        '<div class="modal_header" style="margin-bottom:20px;border-bottom:2px solid #8C271E;padding-bottom:10px;">' +
        '<h2>Item Details</h2>' +
        '</div>' +
        '<div class="detail_row">' +
        '<div class="detail_label">Type</div>' +
        '<div class="detail_value">' +
        '<span class="item_badge badge_' + item.item_type + '">' + item.item_type.toUpperCase() + '</span>' +
        '</div>' +
        '</div>' +
        '<div class="detail_row">' +
        '<div class="detail_label">Status</div>' +
        '<div class="detail_value">' + item.status.charAt(0).toUpperCase() + item.status.slice(1) + '</div>' +
        '</div>' +
        '<div class="detail_row">' +
        '<div class="detail_label">Item Name</div>' +
        '<div class="detail_value" style="font-weight:bold;font-size:1.2em;">' + item.item_name + '</div>' +
        '</div>' +
        '<div class="detail_row">' +
        '<div class="detail_label">Category</div>' +
        '<div class="detail_value">' + item.category + '</div>' +
        '</div>' +
        '<div class="detail_row">' +
        '<div class="detail_label">Date ' + dateLabel + '</div>' +
        '<div class="detail_value">' + item.date_reported + '</div>' +
        '</div>' +
        '<div class="detail_row">' +
        '<div class="detail_label">Location</div>' +
        '<div class="detail_value">' + item.location + '</div>' +
        '</div>' +
        '<div class="detail_row">' +
        '<div class="detail_label">Description</div>' +
        '<div class="detail_value">' + item.description + '</div>' +
        '</div>' +
        '<div class="detail_row">' +
        '<div class="detail_label">Reporter Name</div>' +
        '<div class="detail_value">' + item.reporter_name + '</div>' +
        '</div>' +
        '<div class="detail_row">' +
        '<div class="detail_label">Contact Info</div>' +
        '<div class="detail_value" style="background:#f8f9fa;padding:10px;border-radius:4px;border:1px dashed #8C271E;">' +
        item.reporter_contact +
        '</div>' +
        '</div>' +
        '<div class="detail_actions">' +
        '<button class="btn btn-warning" onclick="handleMarkResolved(' + item.id + ')">Mark as Resolved</button>' +
        '<button class="btn btn-danger" onclick="handleFlagItem(' + item.id + ')" style="background-color:#fab1a0; color:#2d3436;">🚩 Report Fake</button>' +
        '<button class="btn btn-danger" onclick="handleDeleteReport(' + item.id + ')" style="background-color:#d63031;">Delete Report</button>' +
        '<button class="btn btn-danger" onclick="closeDetails()" style="background-color:#636e72;">Close</button>' +
        '</div>';

    detailsModal.style.display = 'block';
}

async function handleFlagItem(id) {
    if (!confirm('Do you want to report this listing as fake or spam?')) return;
    try {
        const res = await apiFetch('/items/' + id + '/flag', { method: 'POST' });
        if (res.deleted) {
            alert('This report has been removed due to multiple community flags.');
            closeDetails();
            await loadItems();
            await loadStats();
        } else {
            alert('Thank you for flagging. This report is under community review.');
        }
    } catch (err) {
        alert('Failed to flag item: ' + err.message);
    }
}
window.handleFlagItem = handleFlagItem;


async function handleMarkResolved(id) {
    try {
        await apiFetch('/items/' + id, {
            method: 'PUT',
            body: JSON.stringify({ status: 'resolved' })
        });
        alert('Item marked as resolved!');
        closeDetails();
        await loadItems();
        await loadStats();
    } catch (err) {
        alert('Failed to update status: ' + err.message);
    }
}
window.handleMarkResolved = handleMarkResolved;

async function handleDeleteReport(id) {
    if (!confirm('Are you sure you want to delete this report? This action cannot be undone.')) return;

    try {
        await apiFetch('/items/' + id, { method: 'DELETE' });
        alert('Report deleted successfully.');
        closeDetails();
        await loadItems();
        await loadStats();
    } catch (err) {
        alert('Failed to delete: ' + err.message);
    }
}
window.handleDeleteReport = handleDeleteReport;

async function loadStats() {
    try {
        var stats = await apiFetch('/stats');
        document.getElementById('lost_count').innerText = stats.active_lost;
        document.getElementById('found_count').innerText = stats.active_found;
        document.getElementById('resolved_count').innerText = stats.resolved;
    } catch (err) {
        console.error('Failed to load stats:', err);
    }
}

window.onclick = function (event) {
    if (event.target === reportModal) closeReportForm();
    if (event.target === detailsModal) closeDetails();
};

document.addEventListener('DOMContentLoaded', async function () {
    reportModal = document.getElementById('report_modal');
    detailsModal = document.getElementById('details_modal');
    lostForm = document.getElementById('lost_form');
    foundForm = document.getElementById('found_form');
    await loadItems();
    await loadStats();
});