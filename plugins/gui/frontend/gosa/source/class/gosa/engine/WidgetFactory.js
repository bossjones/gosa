qx.Class.define("gosa.engine.WidgetFactory", {
  type : "static",

  statics : {

    /**
     * Create a new widget for the given object and invoke the callback afterwards.
     *
     * @param obj {gosa.proxy.Object} The objects.* object for which the widget shall be created
     */
    createWidget : function(obj) {
      qx.core.Assert.assertInstance(obj, gosa.proxy.Object);

      return new qx.Promise(function(resolve, reject) {
        // collect templates
        var templates = [];
        var addTemplates = function(name) {
          qx.lang.Array.append(templates, gosa.util.Template.getTemplateObjects(name));
        };

        addTemplates(obj.baseType);

        // extensions
        if ("extensionTypes" in obj) {
          var extensions = obj.extensionTypes;
          for (var ext in extensions) {
            if (extensions.hasOwnProperty(ext) && extensions[ext]) {
              addTemplates(ext);
            }
          }
        }

        // generate widget
        var widget = new gosa.ui.widgets.ObjectEdit(templates);

        resolve(widget);
      }, this);
    },

    /**
     * Create a new widget for the given workflow and invoke the callback afterwards.
     *
     * @param workflow {gosa.proxy.Object} The workflows.* workflow for which the widget shall be created
     * @param templates {Array} array of templates for the workflow
     * @param translations {Map} translations for the templates
     */
    createWorkflowWidget : function(workflow, templates, translations) {
      qx.core.Assert.assertInstance(workflow, gosa.proxy.Object);

      return new qx.Promise(function(resolve) {
        // generate widget
        var widget = new gosa.ui.widgets.ObjectEdit(templates);
        resolve(widget);
      });
    },

    /**
     * Tries to find and create the dialog from the given name. It is first searched for a corresponding class under
     * {@link gosa.ui.dialogs}. If that is not found, it looks into the transferred cache of dialog templates.
     *
     * @param name {String} Name of the dialog class/template
     * @param controller {gosa.data.ObjectEditController ? null} Optional object controller
     * @return {gosa.ui.dialogs.Dialog | null} The (unopened) dialog widget
     */
    createDialog : function(name, controller) {
      qx.core.Assert.assertString(name);
      if (controller) {
        qx.core.Assert.assertInstance(controller, gosa.data.ObjectEditController);
      }

      var clazzName = name.substring(0, 1).toUpperCase() + name.substring(1);
      var clazz = qx.Class.getByName("gosa.ui.dialogs." + clazzName);

      // directly known class
      if (clazz) {
        var dialog = new clazz();
        dialog.setAutoDispose(true);
        return dialog;
      }

      // find dialog template
      var template = gosa.data.TemplateRegistry.getInstance().getDialogTemplate(name);
      if (template) {
        return new gosa.ui.dialogs.TemplateDialog(template, controller);
      }
      return null;
    }
  }
});
