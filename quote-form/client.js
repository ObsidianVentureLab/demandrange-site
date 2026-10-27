(function(){
  'use strict';
  var form=document.getElementById('quote-request-form');
  if(!form){return;}
  var errorSummary=document.getElementById('form-errors');
  var submit=form.querySelector('button[type="submit"]');
  var phone=form.elements.phone_number;
  var phoneChoice=form.elements.phone_contact;
  var token=form.elements.submission_token;
  var loadField=form.elements.form_load_ms;
  var now=Date.now();
  loadField.value=String(now);
  try{token.value=crypto.randomUUID().replace(/-/g,'_');}catch(e){token.value='dr_'+now+'_'+Math.random().toString(36).slice(2);}
  var params=new URLSearchParams(location.search);
  ['asset_ref','campaign_ref'].forEach(function(name){
    var value=(params.get(name)||'').replace(/[^A-Za-z0-9._-]/g,'').slice(0,64);
    if(form.elements[name]){form.elements[name].value=value;}
  });
  function selected(name){return Array.from(form.querySelectorAll('input[name="'+name+'"]:checked'));}
  function setGroupError(name,message){
    var node=document.getElementById(name+'-error');
    if(node){node.textContent=message||'';node.hidden=!message;}
    var group=document.getElementById(name+'-group');
    if(group){group.setAttribute('aria-invalid',message?'true':'false');}
  }
  function setFieldError(field,message){
    var node=document.getElementById(field.name+'-error');
    if(node){node.textContent=message||'';node.hidden=!message;}
    field.setAttribute('aria-invalid',message?'true':'false');
  }
  function updateSummaries(){
    form.querySelectorAll('[data-multi]').forEach(function(box){
      var items=Array.from(box.querySelectorAll('input[type="checkbox"]:checked'));
      var summary=box.querySelector('.selection-summary');
      if(!items.length){summary.textContent=summary.dataset.placeholder;summary.classList.remove('has-selection');return;}
      var labels=items.map(function(input){return input.dataset.label||input.value;});
      summary.textContent=labels.length<3?labels.join(', '):labels.length+' selected';
      summary.classList.add('has-selection');
    });
  }
  form.querySelectorAll('[data-multi] input').forEach(function(input){input.addEventListener('change',updateSummaries);});
  function validate(){
    var errors=[];
    form.querySelectorAll('.field-error').forEach(function(node){node.textContent='';node.hidden=true;});
    form.querySelectorAll('[aria-invalid]').forEach(function(node){node.setAttribute('aria-invalid','false');});
    if(!form.checkValidity()){
      Array.from(form.elements).forEach(function(field){
        if(field.willValidate&&!field.validity.valid){
          setFieldError(field,field.validationMessage);
          errors.push({field:field,message:field.validationMessage});
        }
      });
    }
    ['industries','regions','seniority'].forEach(function(name){
      if(!selected(name).length){
        var message='Choose at least one option.';
        setGroupError(name,message);
        errors.push({field:document.getElementById(name+'-group'),message:message});
      }
    });
    if(phoneChoice.checked&&!phone.value.trim()){
      var requiredMessage='Enter a phone number or clear the phone-contact option.';
      setFieldError(phone,requiredMessage);errors.push({field:phone,message:requiredMessage});
    }else if(phone.value.trim()&&!phoneChoice.checked){
      var permissionMessage='Choose phone contact or remove the phone number.';
      setFieldError(phone,permissionMessage);errors.push({field:phone,message:permissionMessage});
    }
    var elapsed=Date.now()-Number(loadField.value||0);
    if(elapsed<2500){errors.push({field:null,message:'Please review the form before submitting.'});}
    if(errors.length){
      errorSummary.innerHTML='<strong>Please correct the highlighted fields.</strong><ul>'+errors.map(function(item){return '<li>'+item.message.replace(/[<>&"]/g,function(c){return {'<':'&lt;','>':'&gt;','&':'&amp;','"':'&quot;'}[c];})+'</li>';}).join('')+'</ul>';
      errorSummary.hidden=false;
      var first=errors.find(function(item){return item.field;});
      (first&&first.field?first.field:errorSummary).focus();
      return false;
    }
    errorSummary.hidden=true;
    return true;
  }
  form.addEventListener('submit',function(event){
    if(!validate()){event.preventDefault();return;}
    submit.disabled=true;
    submit.textContent='Sending request…';
  });
  window.addEventListener('pageshow',function(){submit.disabled=false;submit.textContent='Request written scope';});
  updateSummaries();
})();
