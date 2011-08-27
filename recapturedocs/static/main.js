var W3CDOM = (document.createElement && document.getElementsByTagName);

function initFileUploads() {
	if (!W3CDOM) return;
	var fakeFileUpload = document.createElement('div');
	fakeFileUpload.className = 'fakefile';

	fakeFileUpload.innerHTML = '<input class="input" style="padding: 2px;" readonly="readonly" /><input type="Submit" name="button" id="button" value="Browse" class="btnbg" />';
	var x = document.getElementsByTagName('input');
	for (var i=0;i<x.length;i++) {
		if (x[i].type != 'file') continue;
		if (x[i].parentNode.className != 'fileinputs') continue;
		x[i].className = 'file hidden';
		var clone = fakeFileUpload.cloneNode(true);
		x[i].parentNode.appendChild(clone);
		x[i].relatedElement = clone.getElementsByTagName('input')[0];
		x[i].onchange = x[i].onmouseout = function () {
			this.relatedElement.value = this.value;
		}
	}
}

function validate()
{
	var fileName = document.getElementById("pdfFile").value;
	if(fileName.indexOf(".pdf") < 0)
	{
		alert("Please select pdf file.");
		return false;
	} else	{
		$.blockUI({message:$('#overlayDiv').html()});
		setOverlayPos();
		return true;
	}
}


