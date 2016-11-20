/*globals window, RSVP, rJS*/
/*jslint indent: 2, nomen: true, maxlen: 80*/
(function (window, RSVP, rJS) {
  "use strict";
  
  function saveOptionDict(gadget) {
    var option_dict = {
      search_engine: gadget.props.element.querySelector(".options input[name=\"search_engine\"]").value,
      auto_redirect: gadget.props.element.querySelector(".options input[name=\"auto_redirect\"]").checked
    };
    return gadget.setSetting("option", option_dict);
  }

  function setSearchUrl(gadget) {
    return RSVP.Queue()
      .push(function() {
        return gadget.getSetting("option");
      })
      .push(function(option) {
        return gadget.getUrlFor({page: 'bookmark_dispatcher'});
      })
      .push(function(url) {
        url = window.location.origin + window.location.pathname + url + '&search=%s';
        gadget.props.element.getElementsByClassName("search-engine-url")[0].innerHTML = url;
      });
  }

  rJS(window)
    .ready(function (g) {
      g.props = {};
      return g.getElement()
        .push(function (element) {
          g.props.element = element;
        });
    })
    .declareAcquiredMethod("translate", "translate")
    .declareAcquiredMethod("getUrlFor", "getUrlFor")
    .declareAcquiredMethod("redirect", "redirect")
    .declareAcquiredMethod("updateHeader", "updateHeader")
    .declareAcquiredMethod('getSetting', 'getSetting')
    .declareAcquiredMethod("jio_allDocs", "jio_allDocs")
    .declareAcquiredMethod("getSetting", "getSetting")
    .declareAcquiredMethod("setSetting", "setSetting")

    .allowPublicAcquisition('triggerSubmit', function () {
      return this.props.element.querySelector('button').click();
    })

    .declareMethod('triggerSubmit', function () {
      return this.props.element.querySelector('button').click();
    })

    .declareMethod("render", function (options) {
      var gadget = this;
      return RSVP.Queue()
        // Set the URL used to set the Bookmark Manager as a search engine.
        .push(function () {
          return setSearchUrl(gadget);
        })
        // Set elements in form to reflect option dict
        .push(function () {
          return gadget.getSetting("option")
            .push(function(option_dict) {
              if (option_dict) {
                gadget.props.element.querySelector(".options input[name=\"search_engine\"]").value = option_dict.search_engine;
                gadget.props.element.querySelector(".options input[name=\"auto_redirect\"]").checked = option_dict.auto_redirect;
              }
            });
        })
        // Adds a save button
        .push(gadget.updateHeader({title: 'Bookmark Manager Preferences', save_action: true}));
    })
    .onEvent("submit", function () {
      saveOptionDict(this);
    });

}(window, RSVP, rJS));