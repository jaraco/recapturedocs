var W3CDOM = (document.createElement && document.getElementsByTagName);

function init_file_uploads() {
	var fake_file_upload = $('<div>');
	fake_file_upload.attr('class', 'fakefile');
	fake_file_upload.html('<input class="input" style="padding: 2px;" readonly="readonly" /><input type="Submit" name="button" id="button" value="Browse" class="upload-button-background" />');

	var orig_upload = $('input[type=file][:parent.fileinputs]');
	orig_upload.attr('class', 'file hidden');
	orig_upload.parent().append(fake_file_upload);
	var update_value = function() {
		fake_file_upload.find('input.input').attr('value', orig_upload.attr('value'));
	};
	orig_upload.change(update_value);
	orig_upload.mouseout(update_value);
}

function validate()
{
	var fileName = document.getElementById("pdfFile").value;
	if(fileName.indexOf(".pdf") < 0)
	{
		alert("Please select pdf file.");
		return false;
	} else {
		$.blockUI({message:$('#overlayDiv').html()});
		setOverlayPos();
		return true;
	}
}


