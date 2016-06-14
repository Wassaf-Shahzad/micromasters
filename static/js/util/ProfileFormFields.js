// @flow
import React from 'react';
import _ from 'lodash';

import {
  boundDateField,
  boundTextField,
  boundSelectField,
  boundCountrySelectField,
  boundStateSelectField,
  boundRadioGroupField,
} from './profile_edit';
import { EDUCATION_LEVELS } from '../constants';
import LANGUAGE_CODES from '../language_codes';
import INDUSTRIES from '../industries';
import iso3166 from 'iso-3166-2';
import type { Option } from '../flow/generalTypes';

export default class ProfileFormFields extends React.Component {
  constructor(props: Object) {
    super(props);

    // bind our field methods to this
    this.boundTextField = boundTextField.bind(this);
    this.boundSelectField = boundSelectField.bind(this);
    this.boundCountrySelectField = boundCountrySelectField.bind(this);
    this.boundStateSelectField = boundStateSelectField.bind(this);
    this.boundDateField = boundDateField.bind(this);
    this.boundRadioGroupField = boundRadioGroupField.bind(this);

    // options we set (for select components)
    let countryOptions = Object.keys(iso3166.data).map(code => ({
      value: code,
      label: iso3166.data[code]['name']
    }));
    this.countryOptions = _.sortBy(countryOptions, 'label');
    this.genderOptions = [
      { value: 'm', label: 'Male' },
      { value: 'f', label: 'Female' },
      { value: 'o', label: 'Other/Prefer not to say' }
    ];
    let languageOptions = LANGUAGE_CODES.map(language => ({
      value: language.alpha2,
      label: language.English
    }));
    this.languageOptions = _.sortBy(languageOptions, 'label');
    this.privacyOptions = [
      { value: 'public', label: 'Public to the world', helper: `Your MicroMaster’s profile will be 
        visible to all website visitors.` },
      { value: 'public_to_mm', label: "Public to other MicroMaster’s students", helper: `Your profile will be 
        visible to other MicroMaster’s learners, and to MIT faculty and staff.` },
      { value: 'private', label: 'Private', helper: `Your MicroMaster’s profile will only 
        be visible to MIT faculty and staff.` }
    ];
    this.educationLevelOptions = EDUCATION_LEVELS;
    this.industryOptions = INDUSTRIES.map(industry => ({
      value: industry,
      label: industry
    }));
  }
  // type declarations
  boundTextField: Function;
  boundSelectField: Function;
  boundCountrySelectField: Function;
  boundStateSelectField: Function;
  boundDateField: Function;
  boundRadioGroupField: Function;
  countryOptions: Option[];
  genderOptions: Option[];
  languageOptions: Option[];
  privacyOptions: Array<{value: string, label: string, helper: string}>;
  educationLevelOptions: Option[];
  industryOptions: Option[];


  static contextTypes = {
    router: React.PropTypes.object.isRequired
  };

  static propTypes = {
    setDeletionIndex:             React.PropTypes.func,
    setShowWorkDeleteDialog:      React.PropTypes.func,
    setShowEducationDeleteDialog: React.PropTypes.func,
    showSwitch:                   React.PropTypes.bool,
  };

  closeConfirmDeleteDialog: Function = (): void => {
    const {
      setDeletionIndex,
      setShowEducationDeleteDialog,
      setShowWorkDeleteDialog
    } = this.props;
    setShowEducationDeleteDialog(false);
    setShowWorkDeleteDialog(false);
    setDeletionIndex(null);
  }

  openEducationDeleteDialog: Function = (index: number): void => {
    const { setDeletionIndex, setShowEducationDeleteDialog } = this.props;
    setDeletionIndex(index);
    setShowEducationDeleteDialog(true);
  }

  openWorkDeleteDialog:Function = (index: number): void => {
    const { setDeletionIndex, setShowWorkDeleteDialog } = this.props;
    setDeletionIndex(index);
    setShowWorkDeleteDialog(true);
  }
}
