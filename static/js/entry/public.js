/* global SETTINGS: false $:false jQuery: false CURRENT_PAGE_URL: false */
import SendGradesDialog from "../containers/SendGradesDialog"
__webpack_public_path__ = `${SETTINGS.public_path}` // eslint-disable-line no-undef, camelcase
import "rrssb/js/rrssb.js"
import "bootstrap"
import "ajaxchimp"
import _ from "lodash"
import React from "react"
import ReactDOM from "react-dom"
import { MuiThemeProvider, createMuiTheme } from "@material-ui/core/styles"
import { Provider } from "react-redux"

import {
  getEnrollmentShareHash,
  revokeEnrollmentShareHash
} from "../actions/programs"

import CourseListWithPopover from "../components/CourseListWithPopover"
import FacultyCarousel from "../components/FacultyCarousel"
import { setDialogVisibility } from "../actions/signup_dialog"
import {
  setShareDialogVisibility,
  setRecordShareLink
} from "../actions/share_grades_dialog"
import { setRevokeShareDialogVisibility } from "../actions/revoke_shared_records_dialog"
import { setSendDialogVisibility } from "../actions/send_grades_dialog"
import {
  shareGradesDialogStore,
  sendGradesDialogStore,
  signupDialogStore,
  revokeShareGradesDialogStore
} from "../store/configureStore"
import SignupDialog from "../containers/SignupDialog"
import CopyLinkDialog from "../containers/CopyLinkDialog"
import RevokeShareDialog from "../containers/RevokeShareDialog"

// Adding forEach polyfill for IE
if (window.NodeList && !NodeList.prototype.forEach) {
  NodeList.prototype.forEach = Array.prototype.forEach
}

// Program Page course list
const courseListEl = document.querySelector("#courses-component")
let courseList = null
let electivesSetList = null
if (SETTINGS.program) {
  courseList = SETTINGS.program.courses
  electivesSetList = SETTINGS.program.electives_sets
}

if (courseListEl && !_.isEmpty(courseList)) {
  ReactDOM.render(
    <MuiThemeProvider theme={createMuiTheme()}>
      <CourseListWithPopover
        courses={courseList}
        electiveSets={electivesSetList}
      />
    </MuiThemeProvider>,
    courseListEl
  )
}

// Program Page carousel div
const carouselEl = document.querySelector("#faculty-carousel")
let facultyList = null
if (SETTINGS.program) {
  facultyList = SETTINGS.program.faculty
}

if (carouselEl && !_.isEmpty(facultyList)) {
  ReactDOM.render(<FacultyCarousel faculty={facultyList} />, carouselEl)
}

// Toast dialog
const toastClose = document.querySelector(".toast .close")
if (toastClose) {
  toastClose.onclick = () => document.querySelector(".toast").remove()
}

const shareOptionsDiv = document.querySelector(".share-options")
if (shareOptionsDiv) {
  // Share Program Records Link Dialog
  const shareStore = shareGradesDialogStore()
  const shareDialog = document.querySelector("#share-dialog")
  const openShareDialog = () =>
    shareStore.dispatch(setShareDialogVisibility(true))
  const openRevokeShareDialog = () =>
    revokeStore.dispatch(setRevokeShareDialogVisibility(true))
  const shareButtonOnClick = async () => {
    updateEnrollmentShareHash()
    openShareDialog()
  }
  const shareButton = document.querySelector(".open-share-dialog")
  if (shareDialog) {
    shareButton.onclick = shareButtonOnClick
    ReactDOM.render(
      <MuiThemeProvider theme={createMuiTheme()}>
        <Provider store={shareStore}>
          <CopyLinkDialog />
        </Provider>
      </MuiThemeProvider>,
      shareDialog
    )
  }

  const revokeButton = document.querySelector(".revoke-shared-records")
  const revokeButtonOnClick = async () => {
    if (SETTINGS.hash || SETTINGS.absolute_record_share_hash) {
      const data = await revokeEnrollmentShareHash(SETTINGS.enrollment_id)
      if (data && data.success) {
        // eslint-disable-next-line require-atomic-updates
        SETTINGS.absolute_record_share_hash = ""
        // eslint-disable-next-line require-atomic-updates
        SETTINGS.hash = ""

        shareStore.dispatch(setRecordShareLink(""))
        updateButtonDisplays()
      }
    }
  }
  const revokeDialog = document.querySelector("#revoke-dialog")
  const revokeStore = revokeShareGradesDialogStore()
  if (revokeDialog) {
    revokeButton.onclick = openRevokeShareDialog
    ReactDOM.render(
      <MuiThemeProvider theme={createMuiTheme()}>
        <Provider store={revokeStore}>
          <RevokeShareDialog onAllowRevoke={revokeButtonOnClick} />
        </Provider>
      </MuiThemeProvider>,
      revokeDialog
    )
  }

  const allowShareButton = document.querySelector(".allow-record-sharing")
  const updateEnrollmentShareHash = async () => {
    if (!SETTINGS.absolute_record_share_hash && SETTINGS.enrollment_id) {
      const data = await getEnrollmentShareHash(SETTINGS.enrollment_id)
      if (data && data.absolute_path) {
        // eslint-disable-next-line require-atomic-updates
        SETTINGS.absolute_record_share_hash = data.absolute_path
        // eslint-disable-next-line require-atomic-updates
        SETTINGS.hash = data.share_hash

        shareStore.dispatch(setRecordShareLink(data.absolute_path))
        updateButtonDisplays()
      }
    }
  }
  allowShareButton.onclick = updateEnrollmentShareHash

  // Send Program Grades
  const sendStore = sendGradesDialogStore()
  const sendDialog = document.querySelector("#send-dialog")
  const openSendDialog = () => sendStore.dispatch(setSendDialogVisibility(true))
  const sendButton = document.querySelector(".open-send-dialog")
  if (sendDialog) {
    sendButton.onclick = openSendDialog
    ReactDOM.render(
      <MuiThemeProvider theme={createMuiTheme()}>
        <Provider store={sendStore}>
          <SendGradesDialog />
        </Provider>
      </MuiThemeProvider>,
      sendDialog
    )
  }

  // Update button display
  const updateButtonDisplays = () => {
    if (SETTINGS.hash && SETTINGS.absolute_record_share_hash) {
      revokeButton.style.display = "inline-block"
      shareButton.style.display = "inline-block"
      sendButton.style.display = "inline-block"
      allowShareButton.style.display = "none"
    } else {
      revokeButton.style.display = "none"
      shareButton.style.display = "none"
      sendButton.style.display = "none"
      allowShareButton.style.display = "inline-block"
    }
  }
  if (SETTINGS.absolute_record_share_hash) {
    shareStore.dispatch(setRecordShareLink(SETTINGS.absolute_record_share_hash))
  }
  updateButtonDisplays()
}
// Signup dialog
const store = signupDialogStore()

const dialogDiv = document.querySelector("#signup-dialog")

const openDialog = () => store.dispatch(setDialogVisibility(true))

const nodes = [...document.querySelectorAll(".open-signup-dialog")]

const url = new URL(window.location.href)
if (url.searchParams.get("next")) {
  openDialog()
}

nodes.forEach(signUpButton => {
  signUpButton.onclick = openDialog
})

ReactDOM.render(
  <MuiThemeProvider theme={createMuiTheme()}>
    <Provider store={store}>
      <SignupDialog />
    </Provider>
  </MuiThemeProvider>,
  dialogDiv
)

/* =================================
===  MAILCHIMP                 ====
=================================== */
function mailchimpCallback(resp) {
  if (resp.result === "success") {
    $(".subscription-result.success")
      .html(`<i class="icon_check_alt2"></i><br/>${resp.msg}`)
      .fadeIn(1000)
    $(".subscription-result.error").fadeOut(500)
  } else if (resp.result === "error") {
    $(".subscription-result.error")
      .html(`<i class="icon_close_alt2"></i><br/>${resp.msg}`)
      .fadeIn(1000)
  }
}

document.addEventListener("DOMContentLoaded", function() {
  $(".mailchimp").ajaxChimp({
    callback: mailchimpCallback,
    // Replace this with your own mailchimp post URL. Don't remove the "". Just paste the url inside "".
    url:
      "//facebook.us6.list-manage.com/subscribe/post?u=ad81d725159c1f322a0c54837&amp;id=008aee5e78"
  })

  $("#mce-MMERGE4").hide()
  $("#mce-MMERGE3").hide()

  $("input[name=MMERGE2]").click(function() {
    if ($("#university").prop("checked")) {
      $("#mce-MMERGE3").show()
      $("#mce-MMERGE4").hide()
    }
    if ($("#corporation").prop("checked")) {
      $("#mce-MMERGE3").show()
      $("#mce-MMERGE4").hide()
    }
    if ($("#learner").prop("checked")) {
      $("#mce-MMERGE3").hide()
      $("#mce-MMERGE4").hide()
    }
    if ($("#other").prop("checked")) {
      $("#mce-MMERGE3").hide()
      $("#mce-MMERGE4").show()
    }
  })
})

/**
 * Set social media sharing links
 */
document.addEventListener("DOMContentLoaded", function() {
  const description =
    "MicroMasters is a " +
    "new digital credential for online learners. The MicroMasters " +
    "credential will be granted to learners who complete an " +
    "integrated set of graduate-level online courses. With the MicroMasters " +
    "credentials, learners can apply for an accelerated master's degree " +
    "program on campus, at MIT or other top universities."
  const twitterDescription =
    "MITx MicroMasters Programs: a new academic credential " +
    "and a new path to a master’s degree from MIT. Learn more "

  $(".rrssb-buttons").rrssb({
    // required:
    title: "MITx MicroMasters",
    url:   CURRENT_PAGE_URL,

    // optional:
    description: description,
    emailBody:   description + CURRENT_PAGE_URL
  })
  const tweetUrl = `https://twitter.com/intent/tweet?text=${twitterDescription}%20${CURRENT_PAGE_URL}`
  document.querySelector(".rrssb-buttons .rrssb-twitter a").href = tweetUrl
})

/**
 * FAQs accordion on the program page
 */
document.addEventListener("DOMContentLoaded", function() {
  $(".accordion")
    .find(".accordion-toggle")
    .click(function() {
      // Expand or collapse this panel
      $(this)
        .next()
        .slideToggle("fast")
      // Rotate the icon
      $(this)
        .find(".material-icons")
        .toggleClass("rotate")
        .toggleClass("rotate-reset")
      // Hide the other panels and rotate the icons to default
      $(".accordion-content")
        .not($(this).next())
        .slideUp("fast")
        .prev()
        .find(".material-icons")
        .removeClass("rotate-reset")
        .addClass("rotate")
    })
  // All external links should open in new tab
  $('a[href^="https://"], a[href^="http://"] ').attr("target", "_blank")

  if (window.location.hash !== "") {
    $(`a[href="${window.location.hash}"]`)
      .parent()
      .trigger("click")
  }
})
