/*
 * HomeValue — client-side behaviour
 *
 * Responsibilities:
 *   - Mobile navigation toggle
 *   - Client-side validation of the prediction form (mirrors server rules)
 *   - POST to /api/predict, then navigate to the shareable result page
 *   - Loading, error and success states
 *
 * The form degrades gracefully: without JavaScript it performs a normal GET to
 * /result and the server performs the same validation and prediction.
 */
(function () {
  'use strict';

  /* ------------------------------------------------------------------ */
  /* Mobile navigation                                                    */
  /* ------------------------------------------------------------------ */
  function initNav() {
    var toggle = document.getElementById('navToggle');
    var links = document.getElementById('navLinks');
    if (!toggle || !links) return;

    toggle.addEventListener('click', function () {
      var isOpen = links.classList.toggle('is-open');
      toggle.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
    });

    // Close the menu after navigating on small screens
    links.addEventListener('click', function (event) {
      if (event.target.closest('a')) {
        links.classList.remove('is-open');
        toggle.setAttribute('aria-expanded', 'false');
      }
    });

    // Close when focus moves outside the header
    document.addEventListener('click', function (event) {
      if (!event.target.closest('.site-header')) {
        links.classList.remove('is-open');
        toggle.setAttribute('aria-expanded', 'false');
      }
    });
  }

  /* ------------------------------------------------------------------ */
  /* Helpers                                                              */
  /* ------------------------------------------------------------------ */
  var RULES = window.HOMEVALUE_VALIDATION || {};

  var FIELD_MESSAGES = {
    location: 'Select a neighborhood from the list.',
    parking: 'Choose a parking option.',
    property_type: 'Select a property type.'
  };

  function setFieldError(name, message) {
    var wrapper = document.querySelector('[data-field="' + name + '"]');
    var errorNode = document.querySelector('[data-error-for="' + name + '"]');
    if (errorNode) errorNode.textContent = message || '';
    if (wrapper) {
      if (message) wrapper.classList.add('has-error');
      else wrapper.classList.remove('has-error');
    }
  }

  function clearAllErrors() {
    document.querySelectorAll('.field.has-error').forEach(function (el) {
      el.classList.remove('has-error');
    });
    document.querySelectorAll('.field__error').forEach(function (el) {
      el.textContent = '';
    });
  }

  function showFormAlert(message) {
    var alertBox = document.getElementById('formAlert');
    var alertText = document.getElementById('formAlertMessage');
    if (!alertBox || !alertText) return;
    alertText.textContent = message;
    alertBox.style.display = 'flex';
    alertBox.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }

  function hideFormAlert() {
    var alertBox = document.getElementById('formAlert');
    if (alertBox) alertBox.style.display = 'none';
  }

  function announce(message) {
    var status = document.getElementById('formStatus');
    if (status) status.textContent = message;
  }

  function formatNumber(value) {
    return Number(value).toLocaleString('en-US');
  }

  /* ------------------------------------------------------------------ */
  /* Validation                                                           */
  /* ------------------------------------------------------------------ */
  function validateForm(form) {
    clearAllErrors();
    var errors = [];
    var firstInvalid = null;

    // Required categorical fields
    ['location', 'property_type'].forEach(function (name) {
      var field = form.elements[name];
      var value = field ? String(field.value || '').trim() : '';
      if (!value) {
        setFieldError(name, FIELD_MESSAGES[name]);
        errors.push(FIELD_MESSAGES[name]);
        if (!firstInvalid) firstInvalid = field;
      }
    });

    // Parking radio group
    var parking = form.querySelector('input[name="parking"]:checked');
    if (!parking) {
      setFieldError('parking', FIELD_MESSAGES.parking);
      errors.push(FIELD_MESSAGES.parking);
      if (!firstInvalid) firstInvalid = form.querySelector('input[name="parking"]');
    }

    // Numeric fields with bounds from the server-specified config
    Object.keys(RULES).forEach(function (name) {
      var rule = RULES[name];
      var field = form.elements[name];
      if (!field) return;

      var raw = String(field.value == null ? '' : field.value).trim();
      if (raw === '') {
        var requiredMsg = rule.label + ' is required.';
        setFieldError(name, requiredMsg);
        errors.push(requiredMsg);
        if (!firstInvalid) firstInvalid = field;
        return;
      }

      var value = parseFloat(raw.replace(/,/g, ''));
      if (!isFinite(value)) {
        var nanMsg = rule.label + ' must be a number.';
        setFieldError(name, nanMsg);
        errors.push(nanMsg);
        if (!firstInvalid) firstInvalid = field;
        return;
      }

      if (value < rule.min || value > rule.max) {
        var rangeMsg =
          rule.label +
          ' must be between ' +
          formatNumber(rule.min) +
          ' and ' +
          formatNumber(rule.max) +
          '.';
        setFieldError(name, rangeMsg);
        errors.push(rangeMsg);
        if (!firstInvalid) firstInvalid = field;
      }
    });

    // Cross-field check: living area should be plausible for the bedroom count
    var areaRaw = form.elements['area_sqft'] ? form.elements['area_sqft'].value : '';
    var bedsRaw = form.elements['bedrooms'] ? form.elements['bedrooms'].value : '';
    var area = parseFloat(areaRaw);
    var beds = parseFloat(bedsRaw);
    if (isFinite(area) && isFinite(beds) && area < beds * 100) {
      var areaMsg =
        'Living area (' + formatNumber(area) + ' sq ft) is unrealistically small for ' + beds + ' bedrooms.';
      setFieldError('area_sqft', areaMsg);
      errors.push(areaMsg);
      if (!firstInvalid) firstInvalid = form.elements['area_sqft'];
    }

    var lotRaw = form.elements['lot_area_sqft'] ? form.elements['lot_area_sqft'].value : '';
    var lot = parseFloat(lotRaw);
    if (isFinite(lot) && isFinite(area) && lot < area) {
      var lotMsg = 'Lot area cannot be smaller than the living area.';
      setFieldError('lot_area_sqft', lotMsg);
      errors.push(lotMsg);
      if (!firstInvalid) firstInvalid = form.elements['lot_area_sqft'];
    }

    if (errors.length && firstInvalid && typeof firstInvalid.focus === 'function') {
      firstInvalid.focus();
    }

    return errors;
  }

  /* ------------------------------------------------------------------ */
  /* Prediction submission                                                */
  /* ------------------------------------------------------------------ */
  function collectPayload(form) {
    return {
      location: form.elements['location'].value,
      area_sqft: form.elements['area_sqft'].value,
      lot_area_sqft: form.elements['lot_area_sqft'].value,
      bedrooms: form.elements['bedrooms'].value,
      bathrooms: form.elements['bathrooms'].value,
      property_age: form.elements['property_age'].value,
      floors: form.elements['floors'].value,
      parking: (form.querySelector('input[name="parking"]:checked') || {}).value || '',
      property_type: form.elements['property_type'].value
    };
  }

  function buildResultUrl(payload) {
    var params = new URLSearchParams();
    Object.keys(payload).forEach(function (key) {
      params.append(key, payload[key]);
    });
    return '/result?' + params.toString();
  }

  function initPredictForm() {
    var form = document.getElementById('predictForm');
    if (!form) return;

    var submitBtn = document.getElementById('predictSubmit');
    var resetBtn = document.getElementById('resetForm');

    // Clear a field's error as soon as the user edits it
    form.addEventListener('input', function (event) {
      var wrapper = event.target.closest('[data-field]');
      if (wrapper) {
        wrapper.classList.remove('has-error');
        var errorNode = wrapper.querySelector('.field__error');
        if (errorNode) errorNode.textContent = '';
      }
      hideFormAlert();
    });

    if (resetBtn) {
      resetBtn.addEventListener('click', function () {
        clearAllErrors();
        hideFormAlert();
        announce('Form reset to typical values.');
      });
    }

    // Set when a network failure forces us to use the plain GET submission.
    var usePlainSubmit = false;

    form.addEventListener('submit', function (event) {
      // If JS-driven prediction is unavailable, fall back to the plain GET submit
      if (!window.HOMEVALUE_MODEL_READY || !window.fetch || usePlainSubmit) return;

      event.preventDefault();
      hideFormAlert();

      var errors = validateForm(form);
      if (errors.length) {
        showFormAlert(errors[0]);
        announce('The form contains ' + errors.length + ' problem(s).');
        return;
      }

      var payload = collectPayload(form);

      submitBtn.classList.add('is-loading');
      submitBtn.disabled = true;
      announce('Requesting estimate…');

      fetch('/api/predict', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      })
        .then(function (response) {
          return response.json().catch(function () {
            return { success: false, error: 'The server returned an unreadable response.' };
          }).then(function (data) {
            return { status: response.status, data: data };
          });
        })
        .then(function (result) {
          if (!result.data || !result.data.success) {
            var message =
              (result.data && result.data.error) ||
              'The estimate could not be generated. Please review the details and try again.';
            showFormAlert(message);
            announce('Prediction failed.');
            return;
          }

          // Show non-blocking server warnings before moving to the result page
          if (result.data.warnings && result.data.warnings.length) {
            announce('Estimate ready. Note: ' + result.data.warnings.join(' '));
          } else {
            announce('Estimate ready. Opening result page.');
          }

          window.location.href = buildResultUrl(payload);
        })
        .catch(function () {
          // Network failure: fall back to the server-rendered GET flow
          usePlainSubmit = true;
          showFormAlert(
            'Could not reach the prediction service. Retrying with a standard form submission.'
          );
          window.setTimeout(function () {
            form.submit();
          }, 800);
        })
        .finally(function () {
          submitBtn.classList.remove('is-loading');
          submitBtn.disabled = !window.HOMEVALUE_MODEL_READY;
        });
    });
  }

  /* ------------------------------------------------------------------ */
  /* Live price-per-sqft helper on the form page                          */
  /* ------------------------------------------------------------------ */
  function initLiveHint() {
    var areaInput = document.getElementById('area_sqft');
    var lotInput = document.getElementById('lot_area_sqft');
    if (!areaInput || !lotInput) return;

    function refresh() {
      var area = parseFloat(areaInput.value);
      var lot = parseFloat(lotInput.value);
      if (isFinite(area) && isFinite(lot) && area > 0 && lot < area) {
        setFieldError('lot_area_sqft', 'Lot area cannot be smaller than the living area.');
      } else if (isFinite(area) && isFinite(lot) && lot >= area) {
        setFieldError('lot_area_sqft', '');
      }
    }

    areaInput.addEventListener('blur', refresh);
    lotInput.addEventListener('blur', refresh);
  }

  /* ------------------------------------------------------------------ */
  document.addEventListener('DOMContentLoaded', function () {
    initNav();
    initPredictForm();
    initLiveHint();
  });
})();
