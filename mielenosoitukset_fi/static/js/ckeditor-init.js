// ckeditor-init.js
import {
    ClassicEditor,
    AccessibilityHelp,
    Autoformat,
    AutoImage,
    Autosave,
    BalloonToolbar,
    BlockQuote,
    BlockToolbar,
    Bold,
    CloudServices,
    Essentials,
    Heading,
    ImageBlock,
    ImageCaption,
    ImageInline,
    ImageInsertViaUrl,
    ImageResize,
    ImageStyle,
    ImageTextAlternative,
    ImageToolbar,
    ImageUpload,
    Indent,
    IndentBlock,
    Italic,
    Link,
    LinkImage,
    List,
    ListProperties,
    MediaEmbed,
    Paragraph,
    PasteFromOffice,
    SelectAll,
    Table,
    TableCaption,
    TableCellProperties,
    TableColumnResize,
    TableProperties,
    TableToolbar,
    TextTransformation,
    TodoList,
    Underline,
    Undo
  } from 'ckeditor5';
  
  export function initClassicEditor(selector = '#editor', hiddenInputId = 'description', initialData = '<h1>Tähän voit syöttää mielenosoituksen tarkemmat tiedot &lt;3</h1><p>:3</p>') {
    const editorConfig = {
      toolbar: {
        items: [
          'undo', 'redo', '|',
          'heading', '|',
          'bold', 'italic', 'underline', '|',
          'link', 'mediaEmbed', 'insertTable', 'blockQuote', '|',
          'bulletedList', 'numberedList', 'todoList', 'outdent', 'indent'
        ],
        shouldNotGroupWhenFull: true
      },
      plugins: [
        AccessibilityHelp,
        Autoformat,
        AutoImage,
        Autosave,
        BalloonToolbar,
        BlockQuote,
        BlockToolbar,
        Bold,
        CloudServices,
        Essentials,
        Heading,
        ImageBlock,
        ImageCaption,
        ImageInline,
        ImageInsertViaUrl,
        ImageResize,
        ImageStyle,
        ImageTextAlternative,
        ImageToolbar,
        ImageUpload,
        Indent,
        IndentBlock,
        Italic,
        Link,
        LinkImage,
        List,
        ListProperties,
        MediaEmbed,
        Paragraph,
        PasteFromOffice,
        SelectAll,
        Table,
        TableCaption,
        TableCellProperties,
        TableColumnResize,
        TableProperties,
        TableToolbar,
        TextTransformation,
        TodoList,
        Underline,
        Undo
      ],
      balloonToolbar: ['bold', 'italic', '|', 'link', '|', 'bulletedList', 'numberedList'],
      blockToolbar: ['bold', 'italic', '|', 'link', 'insertTable', '|', 'bulletedList', 'numberedList', 'outdent', 'indent'],
      heading: {
        options: [
          { model: 'paragraph', title: 'Leipäteksti', class: 'ck-heading_paragraph' },
          { model: 'heading1', view: 'h1', title: 'Otsikko 1', class: 'ck-heading_heading1' },
          { model: 'heading2', view: 'h2', title: 'Otsikko 2', class: 'ck-heading_heading2' },
          { model: 'heading3', view: 'h3', title: 'Otsikko 3', class: 'ck-heading_heading3' },
          { model: 'heading4', view: 'h4', title: 'Otsikko 4', class: 'ck-heading_heading4' },
          { model: 'heading5', view: 'h5', title: 'Otsikko 5', class: 'ck-heading_heading5' },
          { model: 'heading6', view: 'h6', title: 'Otsikko 6', class: 'ck-heading_heading6' }
        ]
      },
      image: {
        toolbar: [
          'toggleImageCaption',
          'imageTextAlternative',
          '|',
          'imageStyle:inline',
          'imageStyle:wrapText',
          'imageStyle:breakText',
          '|',
          'resizeImage'
        ]
      },
      link: {
        addTargetToExternalLinks: true,
        defaultProtocol: 'https://',
        decorators: {
          toggleDownloadable: {
            mode: 'manual',
            label: 'Downloadable',
            attributes: { download: 'file' }
          }
        }
      },
      list: {
        properties: { styles: true, startIndex: true, reversed: true }
      },
      placeholder: 'Type or paste your content here!',
      table: {
        contentToolbar: ['tableColumn', 'tableRow', 'mergeTableCells', 'tableProperties', 'tableCellProperties']
      }
    };
  
    if (initialData !== null) {
      editorConfig.initialData = initialData;
    }
  
    ClassicEditor
      .create(document.querySelector(selector), editorConfig)
      .then(editor => {
        window.editor = editor; // expose globally if needed
        const hiddenInput = document.getElementById(hiddenInputId);
  
        // Sync editor data to hidden input on change
        editor.model.document.on('change:data', () => {
          if (hiddenInput) {
            hiddenInput.value = editor.getData();
          }
        });
  
        // Initialize editor data from hidden input (if any)
        if (hiddenInput?.value) {
          editor.setData(hiddenInput.value);
        }
      })
      .catch(error => {
        console.error('Error initializing CKEditor:', error);
      });
  }
  
